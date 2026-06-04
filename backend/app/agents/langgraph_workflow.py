"""
LangGraph Workflow — SQL AI Analytics Platform.

Full AI pipeline:
  [Optional] voice_cleaning
  → query_enhancement
  → schema_analysis
  → sql_generation
  → validation           (self-corrects up to 3× on failure)
  → explanation
  → visualization
  → analytics_insights   (when query results are available)
  → response_assembly
  (any failure routes to error_handler)

Author : Member 2 — AI/LLM Engineer
"""

from __future__ import annotations

from typing import TypedDict, Dict, Any, Optional, List

from langgraph.graph import StateGraph, START, END

from ..services.ai.schema_context_builder import SchemaContextBuilder
from ..services.ai.prompt_builder import PromptBuilder
from ..services.ai.llm_service import LLMService, LLMServiceError
from ..services.ai.query_enhancer import QueryEnhancer
from .validator_agent import ValidatorAgent
from .explanation_agent import ExplanationAgent
from .visualization_agent import VisualizationAgent
from .analytics_agent import AnalyticsAgent


# =========================================================
# Pipeline State
# =========================================================

class PipelineState(TypedDict, total=False):
    # ── Input ────────────────────────────────────────────
    user_query: str           # original or voice-cleaned query
    raw_voice_input: str      # raw STT text (set when voice mode)
    schema: Dict[str, Any]
    dialect: str
    mode: str                 # "text" | "voice"
    context_hint: str         # previous query for conversational mode

    # ── Intermediate ─────────────────────────────────────
    enhanced_query: str       # after QueryEnhancer
    schema_context: str
    generated_sql: str

    # Query enhancement metadata
    ambiguities: List[str]
    analytics_hints: List[str]

    # Result data (populated externally if executed)
    result_columns: List[str]
    result_rows: List[List[Any]]

    # ── Output ───────────────────────────────────────────
    explanation: str
    confidence: Dict[str, Any]
    recommended_chart: Dict[str, str]
    analytics_insights: Dict[str, Any]
    final_response: Dict[str, Any]

    # ── Control flow ─────────────────────────────────────
    error: Optional[str]
    status: str
    retry_count: int


# =========================================================
# LangGraph Workflow
# =========================================================

class LangGraphWorkflow:
    """Stateful LangGraph pipeline for NL → SQL analytics generation.

    Services and Agents are instantiated ONCE in ``__init__`` and reused
    across all node calls for maximum efficiency.
    """

    def __init__(self) -> None:
        """Initialise all services and agents once and compile the graph."""

        # Services
        self.schema_builder  = SchemaContextBuilder()
        self.prompt_builder  = PromptBuilder()
        self.llm_service     = LLMService()
        self.query_enhancer  = QueryEnhancer()

        # Agents
        self.validator_agent     = ValidatorAgent()
        self.explanation_agent   = ExplanationAgent()
        self.visualization_agent = VisualizationAgent()
        self.analytics_agent     = AnalyticsAgent(use_llm=True)

        self.graph = StateGraph(PipelineState)
        self._build_graph()
        self.compiled_graph = self.graph.compile()

    # =====================================================
    # Utility
    # =====================================================

    @staticmethod
    def _clean_sql(sql: str) -> str:
        """Strip markdown code fences from LLM output."""
        if not sql:
            return ""
        sql = sql.replace("```sql", "").replace("```", "")
        return sql.strip()

    # =====================================================
    # Nodes
    # =====================================================

    def _query_enhancement_node(self, state: PipelineState) -> PipelineState:
        """Stage 0 — enhance the user query before schema analysis."""
        try:
            result = self.query_enhancer.enhance(
                state["user_query"],
                context_hint=state.get("context_hint"),
            )
            state["enhanced_query"]  = result["enhanced_query"]
            state["ambiguities"]     = result.get("ambiguities", [])
            state["analytics_hints"] = result.get("analytics_hints", [])
            state["status"] = "query_enhanced"
        except Exception as exc:
            # Non-fatal: fall back to original query
            state["enhanced_query"]  = state["user_query"]
            state["ambiguities"]     = []
            state["analytics_hints"] = []
            state["status"] = "query_enhanced"

        return state

    def _schema_analysis_node(self, state: PipelineState) -> PipelineState:
        """Stage 1 — convert raw schema dict to AI-readable context."""
        try:
            # Use the enhanced query for smarter schema filtering
            query_for_filter = state.get("enhanced_query") or state["user_query"]
            filtered_schema = self.schema_builder.filter_relevant_tables(
                state["schema"], query_for_filter
            )
            context = self.schema_builder.build_context(filtered_schema)
            state["schema_context"] = context
            state["status"] = "schema_analyzed"
            state["retry_count"] = 0
        except Exception as exc:
            state["error"]  = f"Schema analysis failed: {exc}"
            state["status"] = "schema_failed"
        return state

    def _sql_generation_node(self, state: PipelineState) -> PipelineState:
        """Stage 2 — generate SQL from enhanced query + schema context."""
        try:
            # Prefer the enhanced query; fall back to original
            query = state.get("enhanced_query") or state["user_query"]

            # Append analytics hints to the prompt if present
            hints = state.get("analytics_hints", [])
            if hints:
                hint_text = " Hints: " + "; ".join(hints)
                query = query + hint_text

            prompt = self.prompt_builder.build_sql_prompt(
                user_query=query,
                schema_context=state["schema_context"],
                dialect=state.get("dialect", "mysql"),
            )

            # Retry correction: include previous error context
            if state.get("retry_count", 0) > 0 and state.get("error"):
                prompt += (
                    f"\n\nYOUR PREVIOUS ATTEMPT FAILED: {state['error']}\n"
                    f"Please correct and return only the fixed SQL query."
                )

            raw_sql     = self.llm_service.send_prompt(prompt)
            cleaned_sql = self._clean_sql(raw_sql)

            state["generated_sql"] = cleaned_sql
            state["status"]        = "sql_generated"
            state["error"]         = None

        except LLMServiceError as exc:
            state["generated_sql"] = ""
            state["error"]         = f"LLM generation failed: {exc}"
            state["status"]        = "sql_failed"

        except Exception as exc:
            state["generated_sql"] = ""
            state["error"]         = f"Unexpected SQL generation error: {exc}"
            state["status"]        = "sql_failed"

        return state

    def _validation_node(self, state: PipelineState) -> PipelineState:
        """Stage 3 — validate generated SQL using ValidatorAgent."""
        sql = state.get("generated_sql", "").strip()

        if not sql:
            state["error"]  = "No SQL query was generated."
            state["status"] = "validation_failed"
            return state

        result = self.validator_agent.validate_sql(sql, state["schema"])

        if result["is_valid"]:
            state["confidence"] = result["confidence"]
            state["status"]     = "validated"
            state["error"]      = None
        else:
            state["error"]        = result["error"]
            state["status"]       = "validation_failed"
            state["retry_count"]  = state.get("retry_count", 0) + 1

        return state

    def _explanation_node(self, state: PipelineState) -> PipelineState:
        """Stage 4 — plain-English explanation using ExplanationAgent."""
        try:
            explanation = self.explanation_agent.explain_query(
                state["generated_sql"],
                state.get("enhanced_query") or state["user_query"],
            )
            state["explanation"] = explanation
            state["status"]      = "explained"
        except Exception as exc:
            state["explanation"] = "Explanation could not be generated."
            state["error"]       = f"Explanation error: {exc}"
            state["status"]      = "explained"
        return state

    def _visualization_node(self, state: PipelineState) -> PipelineState:
        """Stage 5 — chart recommendation using VisualizationAgent."""
        try:
            result_cols = state.get("result_columns", [])
            recommendation = self.visualization_agent.recommend_chart(
                columns=result_cols,
                row_count=len(state.get("result_rows", [])) or 10,
                user_query=state.get("enhanced_query") or state["user_query"],
                sql_query=state.get("generated_sql", ""),
            )
            state["recommended_chart"] = recommendation
            state["status"]            = "visualized"
        except Exception as exc:
            state["recommended_chart"] = {
                "chart_type": "table_only",
                "justification": f"Fallback: {exc}",
            }
            state["status"] = "visualized"
        return state

    def _analytics_insight_node(self, state: PipelineState) -> PipelineState:
        """Stage 6 — generate analytics insights from result data (optional).

        This node only runs meaningful analysis when result_rows are present.
        If no rows have been passed (query not yet executed), it generates a
        stub insight about the SQL query structure instead.
        """
        try:
            columns = state.get("result_columns", [])
            rows    = state.get("result_rows", [])

            if rows and columns:
                insights_result = self.analytics_agent.analyze(
                    columns=columns,
                    rows=rows,
                    user_query=state.get("enhanced_query") or state["user_query"],
                    query_sql=state.get("generated_sql", ""),
                )
            else:
                # No result data yet — return a structural insight
                insights_result = {
                    "success":        True,
                    "insights":       ["SQL query generated and validated successfully."],
                    "trends":         [],
                    "top_performers": [],
                    "anomalies":      [],
                    "summary_stats":  {},
                    "narrative":      "Execute the query to generate data-driven insights.",
                    "row_count":      0,
                    "column_count":   len(columns),
                    "insight_cards":  [],
                }

            state["analytics_insights"] = insights_result
            state["status"]             = "insights_generated"

        except Exception as exc:
            state["analytics_insights"] = {
                "success":  False,
                "insights": ["Analytics insight generation failed."],
                "narrative": str(exc),
            }
            state["status"] = "insights_generated"

        return state

    @staticmethod
    def _response_assembly_node(state: PipelineState) -> PipelineState:
        """Stage 7 — assemble the final structured response."""
        confidence = state.get("confidence", {})
        chart      = state.get("recommended_chart", {})
        insights   = state.get("analytics_insights", {})

        state["final_response"] = {
            "success":           True,
            "user_query":        state.get("user_query"),
            "enhanced_query":    state.get("enhanced_query"),
            "sql":               state.get("generated_sql"),
            "explanation":       state.get("explanation"),
            "confidence_score":  confidence.get("score"),
            "confidence_label":  confidence.get("label"),
            "recommended_chart": chart.get("chart_type"),
            "chart_justification": chart.get("justification"),
            "warnings":          confidence.get("warnings", []),
            "ambiguities":       state.get("ambiguities", []),
            "analytics_hints":   state.get("analytics_hints", []),
            "insights":          insights.get("insights", []),
            "insight_cards":     insights.get("insight_cards", []),
            "narrative":         insights.get("narrative"),
            "status":            state.get("status"),
            "error":             None,
        }
        return state

    @staticmethod
    def _error_node(state: PipelineState) -> PipelineState:
        """Error handler — always returns a clean failed response."""
        state["final_response"] = {
            "success":           False,
            "user_query":        state.get("user_query"),
            "enhanced_query":    state.get("enhanced_query"),
            "sql":               state.get("generated_sql", ""),
            "explanation":       state.get("explanation", ""),
            "confidence_score":  None,
            "confidence_label":  None,
            "recommended_chart": "table_only",
            "warnings":          [],
            "ambiguities":       state.get("ambiguities", []),
            "analytics_hints":   [],
            "insights":          [],
            "insight_cards":     [],
            "narrative":         None,
            "status":            state.get("status"),
            "error":             state.get("error", "Unknown workflow error."),
        }
        return state

    # =====================================================
    # Routing Logic
    # =====================================================

    @staticmethod
    def _route_after_schema(state: PipelineState) -> str:
        return "sql_generation" if state.get("status") == "schema_analyzed" else "error_handler"

    @staticmethod
    def _route_after_validation(state: PipelineState) -> str:
        if state.get("status") == "validated":
            return "explanation_step"
        if state.get("retry_count", 0) < 3:
            return "sql_generation"
        return "error_handler"

    @staticmethod
    def _route_after_explanation(state: PipelineState) -> str:
        return "visualization_step"

    @staticmethod
    def _route_after_visualization(state: PipelineState) -> str:
        return "analytics_insight_step"

    @staticmethod
    def _route_after_analytics(state: PipelineState) -> str:
        return "response_assembly"

    # =====================================================
    # Build Graph
    # =====================================================

    def _build_graph(self) -> None:
        """Register all nodes and wire edges."""
        self.graph.add_node("query_enhancement",    self._query_enhancement_node)
        self.graph.add_node("schema_analysis",      self._schema_analysis_node)
        self.graph.add_node("sql_generation",       self._sql_generation_node)
        self.graph.add_node("validation",           self._validation_node)
        self.graph.add_node("explanation_step",     self._explanation_node)
        self.graph.add_node("visualization_step",   self._visualization_node)
        self.graph.add_node("analytics_insight_step", self._analytics_insight_node)
        self.graph.add_node("response_assembly",    self._response_assembly_node)
        self.graph.add_node("error_handler",        self._error_node)

        # Entry point → query enhancement (always runs first)
        self.graph.add_edge(START, "query_enhancement")
        self.graph.add_edge("query_enhancement", "schema_analysis")

        # Conditional routing
        self.graph.add_conditional_edges("schema_analysis", self._route_after_schema)
        self.graph.add_edge("sql_generation", "validation")
        self.graph.add_conditional_edges("validation",        self._route_after_validation)
        self.graph.add_conditional_edges("explanation_step",  self._route_after_explanation)
        self.graph.add_conditional_edges("visualization_step", self._route_after_visualization)
        self.graph.add_conditional_edges("analytics_insight_step", self._route_after_analytics)

        # Terminal edges
        self.graph.add_edge("response_assembly", END)
        self.graph.add_edge("error_handler",     END)

    # =====================================================
    # Public API
    # =====================================================

    def run_pipeline(
        self,
        user_query: str,
        schema: Dict[str, Any],
        dialect: str = "mysql",
        result_columns: Optional[List[str]] = None,
        result_rows: Optional[List[List[Any]]] = None,
        context_hint: Optional[str] = None,
        mode: str = "text",
    ) -> Dict[str, Any]:
        """Run the full AI pipeline and return the structured response.

        Parameters
        ----------
        user_query : str
            Natural-language question (already cleaned if from voice).
        schema : dict
            Database schema in canonical list-of-tables format.
        dialect : str
            ``"mysql"`` or ``"postgresql"``.
        result_columns : list[str], optional
            Column names from a prior query execution (enables analytics).
        result_rows : list[list], optional
            Data rows from a prior query execution (enables analytics).
        context_hint : str, optional
            Previous query for conversational continuation.
        mode : str
            ``"text"`` (default) or ``"voice"``.
        """
        initial_state: PipelineState = {
            "user_query":        user_query,
            "raw_voice_input":   user_query if mode == "voice" else "",
            "schema":            schema,
            "dialect":           dialect,
            "mode":              mode,
            "context_hint":      context_hint or "",
            "enhanced_query":    "",
            "schema_context":    "",
            "generated_sql":     "",
            "ambiguities":       [],
            "analytics_hints":   [],
            "result_columns":    result_columns or [],
            "result_rows":       result_rows or [],
            "explanation":       "",
            "confidence":        {},
            "recommended_chart": {},
            "analytics_insights": {},
            "final_response":    {},
            "error":             None,
            "status":            "initialized",
            "retry_count":       0,
        }

        try:
            final_state = self.compiled_graph.invoke(initial_state)
            return final_state.get(
                "final_response",
                {"success": False, "error": "Workflow returned no response."},
            )
        except Exception as exc:
            return {
                "success": False,
                "error":   f"Pipeline execution error: {exc}",
            }