"""Tests for analytical SQL semantic checker."""

from app.validators.sql_semantic_checker import check_analytical_sql

BI_QUERY = (
    "Customer Business Intelligence Report with customer_name and total_spending"
)


def test_detects_min_gte_avg_having():
    sql = """
    SELECT customer_id FROM orders o
    GROUP BY customer_id
    HAVING MIN(o.total) >= AVG(o.total)
    """
    issues = check_analytical_sql(sql, BI_QUERY)
    assert any("MIN" in i for i in issues)


def test_detects_missing_customer_name():
    sql = "SELECT customer_id, total_spending FROM customers GROUP BY customer_id"
    issues = check_analytical_sql(sql, BI_QUERY)
    assert any("customer_name" in i for i in issues)


def test_passes_well_structured_bi_sql():
    sql = """
    WITH order_totals AS (
      SELECT o.order_id, o.customer_id, SUM(oi.quantity * oi.price) AS order_total
      FROM orders o JOIN order_items oi ON o.order_id = oi.order_id
      GROUP BY o.order_id, o.customer_id
    ),
    category_qty AS (
      SELECT o.customer_id, p.category, SUM(oi.quantity) AS qty
      FROM orders o JOIN order_items oi ON o.order_id = oi.order_id
      JOIN products p ON oi.product_id = p.product_id
      GROUP BY o.customer_id, p.category
    ),
    most_category AS (
      SELECT customer_id, category AS most_purchased_category
      FROM (
        SELECT customer_id, category,
               ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY qty DESC) AS category_rank
        FROM category_qty
      ) x WHERE category_rank = 1
    ),
    customer_metrics AS (
      SELECT c.customer_id, c.customer_name, SUM(oi.quantity * oi.price) AS total_spending
      FROM customers c
      JOIN orders o ON c.customer_id = o.customer_id
      JOIN order_items oi ON o.order_id = oi.order_id
      JOIN products p ON oi.product_id = p.product_id
      GROUP BY c.customer_id, c.customer_name
      HAVING NOT EXISTS (
        SELECT 1 FROM order_totals ot_low
        WHERE ot_low.customer_id = c.customer_id
          AND ot_low.order_total < (
            SELECT AVG(ot_avg.order_total) FROM order_totals ot_avg
            WHERE ot_avg.customer_id = c.customer_id
          )
      )
    )
    SELECT cm.customer_id, cm.customer_name, cm.total_spending, mc.most_purchased_category,
           (SELECT AVG(ot.order_total) FROM order_totals ot WHERE ot.customer_id = cm.customer_id) AS avg_order_value,
           DENSE_RANK() OVER (ORDER BY cm.total_spending DESC) AS spending_rank
    FROM customer_metrics cm
    JOIN most_category mc ON cm.customer_id = mc.customer_id
    """
    issues = check_analytical_sql(sql, BI_QUERY)
    assert issues == []
