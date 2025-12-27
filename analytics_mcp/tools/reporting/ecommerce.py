# Copyright 2025 Google LLC All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""PM-friendly tools for ecommerce reporting."""

from typing import Any, Dict, Literal, Optional

from analytics_mcp.coordinator import mcp
from analytics_mcp.tools.utils import (
    create_data_api_client,
    get_property_id,
    proto_to_dict,
)
from analytics_mcp.tools.reporting.acquisition import _validate_date_format
from google.analytics import data_v1beta


# Metrics for ecommerce overview
ECOMMERCE_OVERVIEW_METRICS = [
    "totalRevenue",
    "ecommercePurchases",
    "purchaseRevenue",
    "averagePurchaseRevenue",
    "transactions",
    "purchaserConversionRate",
]

# Metrics for product reports
PRODUCT_METRICS = [
    "itemRevenue",
    "itemsPurchased",
    "itemsViewed",
    "itemsAddedToCart",
    "cartToViewRate",
    "purchaseToViewRate",
]


@mcp.tool(
    description="""Get ecommerce overview: revenue, transactions, and conversion metrics.

Shows high-level ecommerce performance for your site.

## Returns
- totalRevenue: Total revenue from all sources
- ecommercePurchases: Number of purchases
- purchaseRevenue: Revenue from purchases only
- averagePurchaseRevenue: Average order value
- transactions: Total transaction count
- purchaserConversionRate: % of users who purchased

## Parameters

### start_date / end_date (string)
Valid: "today", "yesterday", "7daysAgo", "30daysAgo", or "YYYY-MM-DD"

## Examples
- Last 30 days: get_ecommerce_overview()
- Last 7 days: get_ecommerce_overview(start_date="7daysAgo")
- This month: get_ecommerce_overview(start_date="2025-01-01", end_date="today")

## Note
Requires ecommerce tracking to be configured in GA4.
"""
)
async def get_ecommerce_overview(
    start_date: str = "30daysAgo",
    end_date: str = "today",
) -> Dict[str, Any]:
    """Get ecommerce overview with revenue and transaction metrics."""

    _validate_date_format(start_date)
    _validate_date_format(end_date)

    request = data_v1beta.RunReportRequest(
        property=get_property_id(),
        date_ranges=[
            data_v1beta.DateRange(start_date=start_date, end_date=end_date)
        ],
        metrics=[data_v1beta.Metric(name=m) for m in ECOMMERCE_OVERVIEW_METRICS],
    )

    response = await create_data_api_client().run_report(request)
    result = proto_to_dict(response)

    formatted = {
        "date_range": {"start": start_date, "end": end_date},
        "metrics": {},
    }

    if result.get("rows"):
        row = result["rows"][0]
        metric_values = row.get("metric_values", [])
        for i, metric_name in enumerate(ECOMMERCE_OVERVIEW_METRICS):
            if i < len(metric_values):
                formatted["metrics"][metric_name] = metric_values[i].get("value")

    return formatted


@mcp.tool(
    description="""Get top products report: best selling products by revenue or quantity.

Shows product performance ranked by revenue, purchases, or views.

## Returns
- itemRevenue: Revenue from this product
- itemsPurchased: Quantity sold
- itemsViewed: Number of product views
- itemsAddedToCart: Times added to cart
- cartToViewRate: % of views that added to cart
- purchaseToViewRate: % of views that purchased

## Parameters

### group_by (string, default: "product")
- "product": Group by product name
- "category": Group by product category
- "brand": Group by product brand

### start_date / end_date (string)
Valid: "today", "yesterday", "7daysAgo", "30daysAgo", or "YYYY-MM-DD"

### limit (integer, default: 10)
Number of results to return (1-100).

### sort_by (string, default: "revenue")
- "revenue": Sort by item revenue
- "purchases": Sort by quantity sold
- "views": Sort by product views

### filter_product (string, optional)
Filter by product name. Partial match, case-insensitive.

### filter_category (string, optional)
Filter by product category. Partial match, case-insensitive.

## Examples
- Top 10 products by revenue: get_top_products()
- Top categories: get_top_products(group_by="category")
- Most viewed products: get_top_products(sort_by="views", limit=20)
- Products in "shoes" category: get_top_products(filter_category="shoes")

## Note
Requires ecommerce tracking with product data configured in GA4.
"""
)
async def get_top_products(
    group_by: Literal["product", "category", "brand"] = "product",
    start_date: str = "30daysAgo",
    end_date: str = "today",
    limit: int = 10,
    sort_by: Literal["revenue", "purchases", "views"] = "revenue",
    filter_product: Optional[str] = None,
    filter_category: Optional[str] = None,
) -> Dict[str, Any]:
    """Get top products report showing best selling items."""

    _validate_date_format(start_date)
    _validate_date_format(end_date)

    # Map group_by to GA4 dimensions
    dimension_map = {
        "product": "itemName",
        "category": "itemCategory",
        "brand": "itemBrand",
    }

    # Map sort_by to GA4 metrics
    sort_map = {
        "revenue": "itemRevenue",
        "purchases": "itemsPurchased",
        "views": "itemsViewed",
    }

    dimension_name = dimension_map.get(group_by, "itemName")
    sort_metric = sort_map.get(sort_by, "itemRevenue")

    request = data_v1beta.RunReportRequest(
        property=get_property_id(),
        date_ranges=[
            data_v1beta.DateRange(start_date=start_date, end_date=end_date)
        ],
        dimensions=[data_v1beta.Dimension(name=dimension_name)],
        metrics=[data_v1beta.Metric(name=m) for m in PRODUCT_METRICS],
        order_bys=[
            data_v1beta.OrderBy(
                metric=data_v1beta.OrderBy.MetricOrderBy(metric_name=sort_metric),
                desc=True,
            )
        ],
        limit=limit,
    )

    # Build filters
    filters = []

    if filter_product:
        filters.append(
            data_v1beta.FilterExpression(
                filter=data_v1beta.Filter(
                    field_name="itemName",
                    string_filter=data_v1beta.Filter.StringFilter(
                        match_type=data_v1beta.Filter.StringFilter.MatchType.CONTAINS,
                        value=filter_product,
                        case_sensitive=False,
                    ),
                )
            )
        )

    if filter_category:
        filters.append(
            data_v1beta.FilterExpression(
                filter=data_v1beta.Filter(
                    field_name="itemCategory",
                    string_filter=data_v1beta.Filter.StringFilter(
                        match_type=data_v1beta.Filter.StringFilter.MatchType.CONTAINS,
                        value=filter_category,
                        case_sensitive=False,
                    ),
                )
            )
        )

    if filters:
        if len(filters) == 1:
            request.dimension_filter = filters[0]
        else:
            request.dimension_filter = data_v1beta.FilterExpression(
                and_group=data_v1beta.FilterExpressionList(expressions=filters)
            )

    response = await create_data_api_client().run_report(request)
    result = proto_to_dict(response)

    formatted = {
        "date_range": {"start": start_date, "end": end_date},
        "group_by": group_by,
        "sort_by": sort_by,
        "filters_applied": {
            k: v for k, v in {
                "product": filter_product,
                "category": filter_category,
            }.items() if v is not None
        },
        "results": [],
    }

    for row in result.get("rows", []):
        dimension_values = row.get("dimension_values", [])
        metric_values = row.get("metric_values", [])

        entry = {
            group_by: dimension_values[0].get("value") if dimension_values else None,
        }
        for i, metric_name in enumerate(PRODUCT_METRICS):
            if i < len(metric_values):
                entry[metric_name] = metric_values[i].get("value")

        formatted["results"].append(entry)

    formatted["total_results"] = len(formatted["results"])

    return formatted
