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

"""Tools for gathering Google Analytics account and property information."""

from typing import Any, Dict, List

from analytics_mcp.coordinator import mcp
from analytics_mcp.tools.utils import (
    create_admin_api_client,
    create_admin_alpha_api_client,
    get_property_id,
    proto_to_dict,
)
from google.analytics import admin_v1beta, admin_v1alpha


@mcp.tool(title="List links to Google Ads accounts")
async def list_google_ads_links() -> List[Dict[str, Any]]:
    """Returns a list of links to Google Ads accounts for the configured property.

    The property ID is configured via the GA_PROPERTY_ID environment variable.
    """
    request = admin_v1beta.ListGoogleAdsLinksRequest(
        parent=get_property_id()
    )
    # Uses an async list comprehension so the pager returned by
    # list_google_ads_links retrieves all pages.
    links_pager = await create_admin_api_client().list_google_ads_links(
        request=request
    )
    all_pages = [proto_to_dict(link_page) async for link_page in links_pager]
    return all_pages


@mcp.tool(title="Gets details about the configured property")
async def get_property_details() -> Dict[str, Any]:
    """Returns details about the configured property.

    The property ID is configured via the GA_PROPERTY_ID environment variable.
    """
    client = create_admin_api_client()
    request = admin_v1beta.GetPropertyRequest(
        name=get_property_id()
    )
    response = await client.get_property(request=request)
    return proto_to_dict(response)


@mcp.tool(title="Gets property annotations for the configured property")
async def list_property_annotations() -> List[Dict[str, Any]]:
    """Returns annotations for the configured property.

    Annotations are a feature that allows you to leave notes on GA4 for specific dates or periods.
    They are typically used to record service releases, marketing campaign launches or changes,
    and rapid traffic increases or decreases due to external factors.

    The property ID is configured via the GA_PROPERTY_ID environment variable.
    """
    request = admin_v1alpha.ListReportingDataAnnotationsRequest(
        parent=get_property_id()
    )
    annotations_pager = (
        await create_admin_alpha_api_client().list_reporting_data_annotations(
            request=request
        )
    )
    all_pages = [
        proto_to_dict(annotation_page)
        async for annotation_page in annotations_pager
    ]
    return all_pages
