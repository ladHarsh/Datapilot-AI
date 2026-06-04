"""
Query Risk Checker Module
==========================
Aggregates results from SQL Validator, Injection Checker, and Complexity Checker
to produce a unified risk score and execution recommendation.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from app.validators.sql_validator import ValidationResult, ValidationStatus
from app.validators.injection_checker import InjectionCheckResult
from app.validators.complexity_checker import ComplexityResult

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ExecutionRecommendation(str, Enum):
    APPROVE = "approve"
    APPROVE_WITH_CAUTION = "approve_with_caution"
    REJECT = "reject"
    BLOCK = "block"


@dataclass
class RiskAnalysisResult:
    """Unified risk analysis result combining all validator outputs."""
    risk_level: RiskLevel
    risk_score: int                          # 0–100
    recommendation: ExecutionRecommendation
    validation_passed: bool
    injection_safe: bool
    complexity_acceptable: bool
    blocking_reasons: list
    warnings: list
    message: str
    apply_row_limit: bool
    apply_timeout: int                       # seconds
    metadata: dict

    def to_dict(self) -> dict:
        return {
            "risk_level": self.risk_level.value,
            "risk_score": self.risk_score,
            "recommendation": self.recommendation.value,
            "validation_passed": self.validation_passed,
            "injection_safe": self.injection_safe,
            "complexity_acceptable": self.complexity_acceptable,
            "blocking_reasons": self.blocking_reasons,
            "warnings": self.warnings,
            "message": self.message,
            "apply_row_limit": self.apply_row_limit,
            "apply_timeout": self.apply_timeout,
            "metadata": self.metadata,
        }


class RiskChecker:
    """
    Combines all validation results and assigns a unified risk level.

    Risk Scoring Logic:
    - SQL validation failure:    +50 points (immediate block)
    - Injection detection:       +40 points (immediate block)
    - Complexity critical:       +30 points (immediate block)
    - Complexity high:           +20 points (warning)
    - Injection score (partial): scaled proportionally
    - Complexity score:          scaled proportionally

    Risk Levels:
    - 0–24:   LOW    → approve
    - 25–49:  MEDIUM → approve_with_caution
    - 50–74:  HIGH   → reject
    - 75–100: CRITICAL → block
    """

    # Weights for combined score
    VALIDATION_FAIL_WEIGHT = 50
    INJECTION_WEIGHT = 0.4        # injection_score * 0.4
    COMPLEXITY_WEIGHT = 0.3       # complexity_score * 0.3

    def analyze(
        self,
        validation: ValidationResult,
        injection: InjectionCheckResult,
        complexity: ComplexityResult,
    ) -> RiskAnalysisResult:
        """
        Perform unified risk analysis.

        Args:
            validation:  Result from SQLValidator.
            injection:   Result from InjectionChecker.
            complexity:  Result from ComplexityChecker.

        Returns:
            RiskAnalysisResult with risk level and execution recommendation.
        """
        logger.info("RiskChecker: starting unified risk analysis.")

        blocking_reasons = []
        warnings = []
        risk_score = 0

        # ── 1. SQL Validation ─────────────────────────────────────────────────
        validation_passed = validation.status == ValidationStatus.SAFE
        if not validation_passed:
            risk_score += self.VALIDATION_FAIL_WEIGHT
            blocking_reasons.append(
                f"SQL validation failed: {validation.message}"
            )
            logger.warning("RiskChecker: SQL validation FAILED.")

        # ── 2. Injection Detection ────────────────────────────────────────────
        injection_safe = injection.is_safe
        if not injection_safe:
            risk_score += int(injection.injection_score * self.INJECTION_WEIGHT) + 25
            blocking_reasons.append(
                f"SQL injection detected (score={injection.injection_score}): "
                f"{', '.join(injection.detected_patterns)}"
            )
            logger.warning("RiskChecker: injection detected.")
        elif injection.injection_score > 0:
            # Partial injection signals (below threshold but still present)
            risk_score += int(injection.injection_score * self.INJECTION_WEIGHT)
            warnings.append(
                f"Minor injection risk indicators detected (score={injection.injection_score})."
            )

        # ── 3. Complexity Analysis ────────────────────────────────────────────
        complexity_acceptable = complexity.is_acceptable
        if not complexity_acceptable:
            risk_score += 30
            blocking_reasons.append(
                f"Query complexity is critical (score={complexity.complexity_score}): "
                f"{'; '.join(complexity.violations)}"
            )
            logger.warning("RiskChecker: complexity CRITICAL.")
        else:
            risk_score += int(complexity.complexity_score * self.COMPLEXITY_WEIGHT)
            if complexity.complexity_level in ("high", "medium"):
                warnings.extend(complexity.warnings)
            if complexity.violations:
                warnings.extend(complexity.violations)

        # ── 4. Full table scan warning ────────────────────────────────────────
        if complexity.has_full_table_scan_risk:
            warnings.append("Full table scan risk detected — results may be slow.")
            risk_score += 5

        # Cap
        risk_score = min(risk_score, 100)

        # ── 5. Classify risk ──────────────────────────────────────────────────
        risk_level = self._classify_risk(risk_score)
        recommendation = self._recommend(risk_level, bool(blocking_reasons))

        # ── 6. Runtime protection params ─────────────────────────────────────
        apply_row_limit = True  # always enforce row limit
        apply_timeout = complexity.recommended_timeout

        message = self._build_message(risk_level, recommendation, blocking_reasons, warnings)

        logger.info(
            "RiskChecker: risk_level=%s score=%d recommendation=%s",
            risk_level.value, risk_score, recommendation.value,
        )

        return RiskAnalysisResult(
            risk_level=risk_level,
            risk_score=risk_score,
            recommendation=recommendation,
            validation_passed=validation_passed,
            injection_safe=injection_safe,
            complexity_acceptable=complexity_acceptable,
            blocking_reasons=blocking_reasons,
            warnings=warnings,
            message=message,
            apply_row_limit=apply_row_limit,
            apply_timeout=apply_timeout,
            metadata={
                "validation_status": validation.status.value,
                "injection_score": injection.injection_score,
                "complexity_score": complexity.complexity_score,
                "complexity_level": complexity.complexity_level,
                "join_count": complexity.join_count,
                "subquery_depth": complexity.subquery_depth,
            },
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    def _classify_risk(self, score: int) -> RiskLevel:
        if score >= 75:
            return RiskLevel.CRITICAL
        elif score >= 50:
            return RiskLevel.HIGH
        elif score >= 25:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW

    def _recommend(self, risk_level: RiskLevel, has_blocking: bool) -> ExecutionRecommendation:
        if has_blocking or risk_level == RiskLevel.CRITICAL:
            return ExecutionRecommendation.BLOCK
        elif risk_level == RiskLevel.HIGH:
            return ExecutionRecommendation.REJECT
        elif risk_level == RiskLevel.MEDIUM:
            return ExecutionRecommendation.APPROVE_WITH_CAUTION
        else:
            return ExecutionRecommendation.APPROVE

    def _build_message(
        self,
        risk_level: RiskLevel,
        recommendation: ExecutionRecommendation,
        blocking_reasons: list,
        warnings: list,
    ) -> str:
        parts = [f"Risk Level: {risk_level.value.upper()} | Recommendation: {recommendation.value.upper()}"]
        if blocking_reasons:
            parts.append("Blocking Reasons: " + " | ".join(blocking_reasons))
        if warnings:
            parts.append("Warnings: " + " | ".join(warnings))
        return " — ".join(parts)


# ── Module-level convenience function ─────────────────────────────────────────

def analyze_risk(
    validation_dict: dict,
    injection_dict: dict,
    complexity_dict: dict,
) -> dict:
    """
    Convenience function accepting raw dicts (e.g., from API layer).

    Reconstructs dataclass objects and runs full risk analysis.
    """
    from app.validators.sql_validator import ValidationStatus, BlockedReason

    val = ValidationResult(
        status=ValidationStatus(validation_dict["status"]),
        statement_type=validation_dict.get("statement_type"),
        is_read_only=validation_dict.get("is_read_only", False),
        message=validation_dict.get("message", ""),
        blocked_reason=(
            BlockedReason(validation_dict["blocked_reason"])
            if validation_dict.get("blocked_reason")
            else None
        ),
        raw_query=validation_dict.get("raw_query", ""),
        normalized_query=validation_dict.get("normalized_query", ""),
    )

    inj = InjectionCheckResult(
        is_safe=injection_dict["is_safe"],
        detected_patterns=injection_dict.get("detected_patterns", []),
        risk_indicators=injection_dict.get("risk_indicators", []),
        sanitized_query=injection_dict.get("sanitized_query", ""),
        message=injection_dict.get("message", ""),
        injection_score=injection_dict.get("injection_score", 0),
    )

    comp = ComplexityResult(
        is_acceptable=complexity_dict["is_acceptable"],
        complexity_score=complexity_dict.get("complexity_score", 0),
        complexity_level=complexity_dict.get("complexity_level", "low"),
        join_count=complexity_dict.get("join_count", 0),
        subquery_depth=complexity_dict.get("subquery_depth", 0),
        union_count=complexity_dict.get("union_count", 0),
        has_full_table_scan_risk=complexity_dict.get("has_full_table_scan_risk", False),
        query_length=complexity_dict.get("query_length", 0),
        violations=complexity_dict.get("violations", []),
        warnings=complexity_dict.get("warnings", []),
        recommended_timeout=complexity_dict.get("recommended_timeout", 30),
        message=complexity_dict.get("message", ""),
    )

    checker = RiskChecker()
    return checker.analyze(val, inj, comp).to_dict()
