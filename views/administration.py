"""Administration views."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import streamlit as st


def render_administration(
    *,
    nav_key: str,
    admin_mode: bool,
    page_header: Callable[[str, str, str], Any],
    test_bitdefender_connection: Callable[[], dict[str, Any]],
    get_bitdefender_endpoint_inventory: Callable[[], list[dict[str, Any]]],
    build_bitdefender_diagnostics: Callable[[list[dict[str, Any]]], dict[str, Any]],
    load_computer_assets: Callable[[str], Any],
    computer_asset_list_name: str,
    map_computers_with_inventory: Callable[
        [list[dict[str, Any]], Callable[[], list[dict[str, Any]]]],
        list[dict[str, Any]],
    ],
    build_computer_mapping_diagnostics: Callable[[list[dict[str, Any]]], dict[str, int]],
    bitdefender_error_type: type[Exception],
) -> None:
    """Render Administration tools, including a read-only GravityZone probe."""
    if not admin_mode:
        st.error("Administrator access is required.")
        return

    admin_pages = {
        "admin_users": ("👥", "Users", "จัดการผู้ใช้และสิทธิ์การเข้าถึง"),
        "admin_settings": ("⚙", "Settings", "การตั้งค่าระบบและการเชื่อมต่อ"),
        "admin_logs": ("📜", "Activity Logs", "บันทึกกิจกรรมและการตรวจสอบ"),
    }
    icon, title, subtitle = admin_pages.get(nav_key, ("⚙", "Administration", ""))
    page_header(icon, title, subtitle)

    if nav_key != "admin_settings":
        st.markdown("""
        <div style="background:rgba(255,255,255,.92);backdrop-filter:blur(16px);border-radius:16px;
            padding:2rem 2.2rem;border:1px solid #e2e8f0;box-shadow:0 8px 32px rgba(99,102,241,.08);">
            <div style="font-size:2.5rem;margin-bottom:12px;">🚧</div>
            <h3 style="color:#201f1e;margin:0 0 8px;font-size:1.1rem;">Coming soon</h3>
            <p style="color:#605e5c;margin:0;font-size:0.9rem;">
                ส่วนนี้อยู่ระหว่างพัฒนา — ฟีเจอร์จะเปิดใช้งานในรุ่นถัดไป
            </p>
        </div>
        """, unsafe_allow_html=True)
        return

    st.subheader("Bitdefender API Test")
    st.caption("Read-only connection test for Bitdefender GravityZone endpoints.")

    if st.button("Test Bitdefender Connection", key="admin_test_bitdefender_connection"):
        try:
            result = test_bitdefender_connection()
        except bitdefender_error_type as exc:
            st.error(f"Bitdefender connection failed: {exc}")
        except Exception:
            st.error("Bitdefender connection failed due to an unexpected error. Check the application logs.")
        else:
            st.success("Connected successfully")
            total_col, pages_col = st.columns(2)
            total_col.metric("Total Endpoints", result.get("total", 0))
            pages_col.metric("Pages Count", result.get("pagesCount", 0))
            st.markdown("**Sample Endpoint JSON**")
            sample = result.get("sample")
            if sample is None:
                st.info("No managed endpoint sample was returned.")
            else:
                st.json(sample)

            try:
                endpoints = get_bitdefender_endpoint_inventory()
                diagnostics = build_bitdefender_diagnostics(endpoints)
            except bitdefender_error_type as exc:
                st.error(f"Endpoint diagnostics failed: {exc}")
            except Exception:
                st.error("Endpoint diagnostics failed due to an unexpected error. Check the application logs.")
            else:
                st.markdown("### Mapping Diagnostic Summary")
                summary_columns = st.columns(3)
                summary_columns[0].metric(
                    "Total Managed Endpoints",
                    diagnostics["total_managed_endpoints"],
                )
                summary_columns[1].metric(
                    "Endpoints with hostname",
                    diagnostics["endpoints_with_hostname"],
                )
                summary_columns[2].metric(
                    "Endpoints with username",
                    diagnostics["endpoints_with_username"],
                )
                summary_columns = st.columns(3)
                summary_columns[0].metric(
                    "Endpoints with policy name",
                    diagnostics["endpoints_with_policy_name"],
                )
                summary_columns[1].metric(
                    "Endpoints missing policy",
                    diagnostics["endpoints_missing_policy"],
                )
                summary_columns[2].metric(
                    "Duplicate normalized hostnames",
                    diagnostics["duplicate_normalized_hostnames"],
                )

                st.markdown("### Endpoint Mapping Fields (sample)")
                mapping_fields = [
                    {
                        "Endpoint Name": endpoint.get("endpoint_name", ""),
                        "Hostname": endpoint.get("hostname") or endpoint.get("fqdn", ""),
                        "Username": ", ".join(endpoint.get("usernames") or []),
                        "Policy Name": endpoint.get("policy_name", ""),
                        "Managed": endpoint.get("managed", ""),
                        "Last Seen": endpoint.get("last_seen", ""),
                    }
                    for endpoint in endpoints[:10]
                ]
                if mapping_fields:
                    st.dataframe(mapping_fields, use_container_width=True, hide_index=True)
                else:
                    st.info("No managed endpoints were returned for mapping diagnostics.")

                duplicates = diagnostics["duplicate_hostnames"]
                if duplicates:
                    st.markdown("### Duplicate Hostnames")
                    st.dataframe(duplicates, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("Computer Asset → Bitdefender Mapping Preview")
    st.caption("Read-only deterministic preview. No endpoint or policy is modified.")

    if st.button(
        "Preview Computer → Bitdefender Mapping",
        key="admin_preview_bitdefender_mapping",
    ):
        try:
            computer_data = load_computer_assets(computer_asset_list_name)
            if hasattr(computer_data, "to_dict"):
                computer_records = computer_data.to_dict(orient="records")
            else:
                computer_records = list(computer_data or [])
            mappings = map_computers_with_inventory(
                computer_records,
                get_bitdefender_endpoint_inventory,
            )
        except bitdefender_error_type as exc:
            st.error(f"Computer mapping preview failed: {exc}")
        except Exception:
            st.error("Computer mapping preview failed due to an unexpected error. Check the application logs.")
        else:
            st.session_state["bitdefender_computer_mapping_preview"] = mappings

    mappings = st.session_state.get("bitdefender_computer_mapping_preview")
    if mappings is not None:
        diagnostics = build_computer_mapping_diagnostics(mappings)
        st.markdown("### Computer Mapping Summary")
        metric_rows = (
            (
                ("Total Computer Assets", "total_computer_assets"),
                ("Matched", "matched"),
                ("Missing Bitdefender Policy", "missing_policy"),
            ),
            (
                ("Hostname Exact", "hostname_exact"),
                ("Hostname Normalized", "hostname_normalized"),
                ("Username Match", "username_match"),
            ),
            (
                ("Duplicate Hostname", "duplicate_hostname"),
                ("Ambiguous Username", "ambiguous_username"),
                ("Not Found", "not_found"),
            ),
        )
        for metric_row in metric_rows:
            metric_columns = st.columns(3)
            for column, (label, key) in zip(metric_columns, metric_row):
                column.metric(label, diagnostics[key])
        if diagnostics["insufficient_asset_data"]:
            st.caption(
                f"Insufficient Asset Data: {diagnostics['insufficient_asset_data']}"
            )

        filter_name = st.selectbox(
            "Mapping Filter",
            ["All", "Matched", "Manual Review", "Not Found", "Missing Policy"],
            key="admin_bitdefender_mapping_filter",
        )
        if filter_name == "Matched":
            filtered_mappings = [row for row in mappings if row.get("matched")]
        elif filter_name == "Manual Review":
            filtered_mappings = [
                row for row in mappings if row.get("match_confidence") == "manual_review"
            ]
        elif filter_name == "Not Found":
            filtered_mappings = [
                row
                for row in mappings
                if row.get("match_status") in ("Not Found", "Insufficient Asset Data")
            ]
        elif filter_name == "Missing Policy":
            filtered_mappings = [row for row in mappings if row.get("policy_missing")]
        else:
            filtered_mappings = mappings

        preview_rows = [
            {
                "Employee": row.get("employee_name", ""),
                "Computer Hostname": row.get("computer_hostname", ""),
                "LoginAccount": row.get("login_account", ""),
                "Endpoint": row.get("endpoint_name", ""),
                "Endpoint Hostname": row.get("endpoint_hostname", ""),
                "Bitdefender Policy": row.get("policy_name", ""),
                "Match Status": row.get("match_status", ""),
                "Confidence": row.get("match_confidence", ""),
                "Candidate Count": row.get("candidate_count", 0),
            }
            for row in filtered_mappings
        ]
        st.dataframe(preview_rows, use_container_width=True, hide_index=True)

        manual_rows = [row for row in filtered_mappings if row.get("candidates")]
        if manual_rows:
            st.markdown("### Manual Review Candidates")
            for index, row in enumerate(manual_rows, start=1):
                label = (
                    f"{row.get('computer_hostname') or row.get('login_account') or 'Unknown asset'} "
                    f"— {row.get('match_status')} ({row.get('candidate_count', 0)})"
                )
                with st.expander(label, expanded=False):
                    st.json(row["candidates"])
