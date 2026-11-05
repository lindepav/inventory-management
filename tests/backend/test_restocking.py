"""
Tests for restocking endpoints.
"""
import pytest

import mock_data


@pytest.fixture(autouse=True)
def reset_restock_orders():
    """Submitted orders are in-memory module state; isolate each test."""
    mock_data.restock_orders.clear()
    yield
    mock_data.restock_orders.clear()


class TestRestockRecommendations:
    """Tests for GET /api/restocking/recommendations"""

    def test_zero_budget_returns_empty(self, client):
        response = client.get("/api/restocking/recommendations?budget=0")
        assert response.status_code == 200
        assert response.json() == []

    def test_negative_budget_rejected(self, client):
        response = client.get("/api/restocking/recommendations?budget=-5")
        assert response.status_code == 400

    def test_recommendations_fit_budget(self, client):
        budget = 5000
        response = client.get(f"/api/restocking/recommendations?budget={budget}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        assert sum(i["line_cost"] for i in data) <= budget
        for item in data:
            assert 0 < item["recommended_qty"] <= item["shortfall"]

    def test_ranked_by_shortfall(self, client):
        data = client.get("/api/restocking/recommendations?budget=1000000").json()
        shortfalls = [i["shortfall"] for i in data]
        assert shortfalls == sorted(shortfalls, reverse=True)

    def test_large_budget_covers_full_shortfall(self, client):
        data = client.get("/api/restocking/recommendations?budget=1000000").json()
        for item in data:
            assert item["recommended_qty"] == item["shortfall"]


class TestRestockOrders:
    """Tests for POST/GET /api/restocking/orders"""

    def test_create_order(self, client):
        payload = {
            "items": [{"sku": "WDG-001", "quantity": 10}, {"sku": "MTR-304", "quantity": 1}],
            "budget": 1000,
        }
        response = client.post("/api/restocking/orders", json=payload)
        assert response.status_code == 201
        order = response.json()
        assert order["status"] == "Submitted"
        assert order["total_cost"] == pytest.approx(10 * 18.50 + 310.00)
        # Lead time is the longest item lead time (MTR-304 = 35 days)
        assert order["lead_time_days"] == 35
        assert order["expected_delivery"]

    def test_over_budget_rejected(self, client):
        payload = {"items": [{"sku": "MTR-304", "quantity": 10}], "budget": 100}
        assert client.post("/api/restocking/orders", json=payload).status_code == 400

    def test_unknown_sku_rejected(self, client):
        payload = {"items": [{"sku": "NOPE-1", "quantity": 1}], "budget": 100}
        assert client.post("/api/restocking/orders", json=payload).status_code == 400

    def test_zero_quantity_rejected(self, client):
        payload = {"items": [{"sku": "WDG-001", "quantity": 0}], "budget": 100}
        assert client.post("/api/restocking/orders", json=payload).status_code == 400

    def test_empty_order_rejected(self, client):
        assert client.post("/api/restocking/orders", json={"items": [], "budget": 100}).status_code == 400

    def test_list_orders_newest_first(self, client):
        for qty in (1, 2):
            client.post("/api/restocking/orders", json={"items": [{"sku": "WDG-001", "quantity": qty}], "budget": 100})
        data = client.get("/api/restocking/orders").json()
        assert [o["items"][0]["quantity"] for o in data] == [2, 1]
