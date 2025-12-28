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

"""Tools for running core reports using the Data API."""

from typing import Any, Dict, List

from analytics_mcp.coordinator import mcp
from analytics_mcp.tools.utils import (
    create_data_api_client,
    get_property_id,
    proto_to_dict,
)
from google.analytics import data_v1beta


_RUN_REPORT_DESCRIPTION = """Run a GA4 Data API report with custom dimensions, metrics, filters, and sorting.

For filter/date/orderby JSON examples, call get_api_hints first.

Args:
  date_ranges: List of {start_date, end_date, name?}. Dates: "today", "yesterday", "NdaysAgo", or "YYYY-MM-DD".
  dimensions: Dimension names from https://developers.google.com/analytics/devguides/reporting/data/v1/api-schema#dimensions
  metrics: Metric names from https://developers.google.com/analytics/devguides/reporting/data/v1/api-schema#metrics
  dimension_filter: FilterExpression for dimensions (get_api_hints for examples)
  metric_filter: FilterExpression for metrics (get_api_hints for examples)
  order_bys: List of OrderBy objects (get_api_hints for examples)
  limit: Max rows (1-250000)
  offset: Starting row (0-indexed)
  currency_code: ISO4217 code (e.g., "USD")
  return_property_quota: Include quota info

For custom dimensions/metrics, call get_custom_dimensions_and_metrics.
"""


async def run_report(
    date_ranges: List[Dict[str, str]],
    dimensions: List[str],
    metrics: List[str],
    dimension_filter: Dict[str, Any] = None,
    metric_filter: Dict[str, Any] = None,
    order_bys: List[Dict[str, Any]] = None,
    limit: int = None,
    offset: int = None,
    currency_code: str = None,
    return_property_quota: bool = False,
) -> Dict[str, Any]:
    """Runs a Google Analytics Data API report."""
    request = data_v1beta.RunReportRequest(
        property=get_property_id(),
        dimensions=[
            data_v1beta.Dimension(name=dimension) for dimension in dimensions
        ],
        metrics=[data_v1beta.Metric(name=metric) for metric in metrics],
        date_ranges=[data_v1beta.DateRange(dr) for dr in date_ranges],
        return_property_quota=return_property_quota,
    )

    if dimension_filter:
        request.dimension_filter = data_v1beta.FilterExpression(
            dimension_filter
        )

    if metric_filter:
        request.metric_filter = data_v1beta.FilterExpression(metric_filter)

    if order_bys:
        request.order_bys = [
            data_v1beta.OrderBy(order_by) for order_by in order_bys
        ]

    if limit:
        request.limit = limit
    if offset:
        request.offset = offset
    if currency_code:
        request.currency_code = currency_code

    response = await create_data_api_client().run_report(request)

    return proto_to_dict(response)


mcp.add_tool(
    run_report,
    title="Run a Google Analytics Data API report",
    description=_RUN_REPORT_DESCRIPTION,
)
