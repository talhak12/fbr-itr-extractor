import streamlit as st
import pdfplumber
import pandas as pd
import json
import re


# ─────────────────────────────────────────────
#  FUNCTIONS
# ─────────────────────────────────────────────

def extract_rows(pdf_path, search_term):
    results = []
    term_lower = search_term.lower()

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            for table in page.extract_tables():
                for row in table:
                    clean_row = [str(c).strip() if c else "" for c in row]
                    if term_lower in " ".join(clean_row).lower():
                        result = {
                            "page"                   : page_num,
                            "description"            : clean_row[0] if len(clean_row) > 0 else "",
                            "code"                   : clean_row[1] if len(clean_row) > 1 else "",
                            "receipts_value"         : clean_row[2] if len(clean_row) > 2 else "",
                            "tax_collected_deducted" : clean_row[3] if len(clean_row) > 3 else "",
                            "tax_chargeable"         : clean_row[4] if len(clean_row) > 4 else "",
                        }
                        results.append(result)
    return results


def calculate_receipts(description, tax_collected_deducted):
    match = re.search(r'@\s*([\d.]+)\s*%', description)
    if not match:
        return None, None

    rate_str = match.group(1)
    rate = float(rate_str) / 100
    tax = float(str(tax_collected_deducted).replace(",", "").strip())

    if rate == 0 or tax == 0:
        return None, None

    receipts = tax / rate
    return round(receipts, 2), rate_str


# ─────────────────────────────────────────────
#  STREAMLIT UI
# ─────────────────────────────────────────────

st.set_page_config(page_title="FBR ITR Extractor", page_icon="📄", layout="wide")

st.title("📄 FBR ITR PDF Extractor")
st.markdown("Upload any FBR Income Tax Return PDF and extract specific rows instantly.")

st.divider()

# ── Left and Right columns ──
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("⚙️ Settings")

    # File upload
    uploaded_file = st.file_uploader("Upload FBR ITR PDF", type=["pdf"])

    # Search terms
    st.markdown("**Search Terms**")
    st.caption("Add or remove terms as needed")

    # Default search terms
    if "search_terms" not in st.session_state:
        st.session_state.search_terms = [
            "Import u/s 148",
            "Net Purchases",
            "Net Import Raw Material"
        ]

    # Show each search term with a remove button
    for i, term in enumerate(st.session_state.search_terms):
        col_term, col_remove = st.columns([4, 1])
        with col_term:
            st.session_state.search_terms[i] = st.text_input(
                f"Term {i+1}", 
                value=term, 
                key=f"term_{i}",
                label_visibility="collapsed"
            )
        with col_remove:
            if st.button("❌", key=f"remove_{i}"):
                st.session_state.search_terms.pop(i)
                st.rerun()

    # Add new term button
    if st.button("➕ Add Search Term"):
        st.session_state.search_terms.append("")
        st.rerun()

    st.divider()

    # Extract button
    extract_btn = st.button("🔍 Extract Data", type="primary", use_container_width=True)


with col2:
    st.subheader("📋 Results")

    if extract_btn:
        if uploaded_file is None:
            st.error("❌ Please upload a PDF file first!")
        else:
            # Save uploaded file temporarily
            temp_path = f"/tmp/{uploaded_file.name}"
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.read())

            # Extract all search terms
            all_results = []
            progress = st.progress(0, text="Extracting...")

            for i, term in enumerate(st.session_state.search_terms):
                if term.strip():
                    rows = extract_rows(temp_path, term)
                    all_results.extend(rows)
                progress.progress((i + 1) / len(st.session_state.search_terms),
                                   text=f"Searching: '{term}'")

            progress.empty()

            # Back-calculate receipts where value is 0
            for r in all_results:
                if str(r["receipts_value"]).strip() in ("0", "", "0.0"):
                    calculated, rate_str = calculate_receipts(
                        r["description"], r["tax_collected_deducted"]
                    )
                    if calculated:
                        r["calculated_receipts_value"] = f"{calculated:,.0f}"
                    else:
                        r["calculated_receipts_value"] = "N/A"
                else:
                    r["calculated_receipts_value"] = "N/A - already has value"

            if all_results:
                st.success(f"✅ Found {len(all_results)} row(s)")

                # Show table
                df = pd.DataFrame(all_results)
                st.dataframe(df, use_container_width=True)

                st.divider()

                # ── Download buttons side by side ──
                dl_col1, dl_col2 = st.columns(2)

                with dl_col1:
                    # Download JSON
                    json_str = json.dumps(all_results, indent=2)
                    st.download_button(
                        label="⬇️ Download JSON",
                        data=json_str,
                        file_name="fbr_extracted_data.json",
                        mime="application/json",
                        use_container_width=True
                    )

                with dl_col2:
                    # Download CSV
                    csv_str = df.to_csv(index=False)
                    st.download_button(
                        label="⬇️ Download CSV",
                        data=csv_str,
                        file_name="fbr_extracted_data.csv",
                        mime="text/csv",
                        use_container_width=True
                    )

                st.divider()

                # Show JSON preview
                st.subheader("🔍 JSON Preview")
                st.json(all_results)

            else:
                st.warning("⚠️ No matching rows found. Try different search terms.")
    else:
        st.info("👈 Upload a PDF and click **Extract Data** to start")