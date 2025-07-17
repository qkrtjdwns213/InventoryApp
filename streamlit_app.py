import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

json_key = st.secrets["google"]  # [google] 섹션 읽기
creds = ServiceAccountCredentials.from_json_keyfile_dict(json_key, scope)

gc = gspread.authorize(creds)

# 스프레드시트 및 워크시트 이름
SPREADSHEET_NAME = "재고관리"
INVT_WKS   = "Inventory"
TRANS_WKS = "Transactions"
PAJU_WKS  = "출고"

# 워크시트 연결
sh       = gc.open(SPREADSHEET_NAME)
ws_inv   = sh.worksheet(INVT_WKS)
ws_trans = sh.worksheet(TRANS_WKS)
ws_paju  = sh.worksheet(PAJU_WKS)

@st.cache_data
def load_inventory():
    df = pd.DataFrame(ws_inv.get_all_records())
    df['ISBN'] = df['ISBN'].astype(str)
    return df.set_index('ISBN')

@st.cache_data
def load_transactions():
    return pd.DataFrame(ws_trans.get_all_records())

@st.cache_data
def load_paju_summary():
    trans = load_transactions()
    paju = trans[trans['Type'] == 'OUT-PAJU'].copy()
    summary = (
        paju
        .groupby(['ISBN','Title'])['Change']
        .agg(lambda x: -x.sum())
        .reset_index()
    )
    return summary

def save_inventory(df):
    # Inventory 시트 업데이트
    ws_inv.clear()
    ws_inv.append_row(df.reset_index().columns.tolist())
    for row in df.reset_index().itertuples(index=False):
        ws_inv.append_row(list(row))

def log_transaction(isbn, title, change, ttype):
    # Transactions 시트에 로그 추가
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ws_trans.append_row([now, isbn, title, change, ttype])

st.title("📚 재고관리 시스템")

tab1, tab2, tab3, tab4 = st.tabs(
    ["입고", "출고", "파주출고", "현재고"]
)

inv_df   = load_inventory()
trans_df = load_transactions()

with tab1:
    st.header("입고")
    cols = st.columns([2,1])
    with cols[0]:
        isbn_in = st.text_input("ISBN 입력")
        if isbn_in and isbn_in not in inv_df.index:
            title_in  = st.text_input("새 책 제목", key="new_title")
            author_in = st.text_input("새 책 저자", key="new_author")
            price_in  = st.number_input("단가", min_value=0, step=100, key="new_price")
        qty_in = st.number_input("수량", value=1, min_value=1, step=1, key="in_qty")
        if st.button("입고"):
            if isbn_in not in inv_df.index:
                inv_df.loc[isbn_in] = [author_in, price_in, title_in, qty_in]
            else:
                inv_df.at[isbn_in, 'qty'] += qty_in
            save_inventory(inv_df)
            log_transaction(isbn_in, inv_df.at[isbn_in,'Title'], qty_in, "IN")
            st.success("입고 완료")
    st.subheader("입고 내역")
    st.dataframe(
        trans_df[trans_df['Type']=="IN"]
        .sort_values(by='Date', ascending=False)
    )

with tab2:
    st.header("출고")
    isbn_out = st.text_input("ISBN 입력", key="out_isbn")
    qty_out  = st.number_input("수량", value=1, min_value=1, step=1, key="out_qty")
    if st.button("출고"):
        if isbn_out not in inv_df.index:
            st.error("등록되지 않은 ISBN")
        elif inv_df.at[isbn_out,'qty'] < qty_out:
            st.error("재고 부족")
        else:
            inv_df.at[isbn_out,'qty'] -= qty_out
            save_inventory(inv_df)
            log_transaction(isbn_out, inv_df.at[isbn_out,'Title'], -qty_out, "OUT")
            st.success("출고 완료")
    st.subheader("출고 내역")
    st.dataframe(
        trans_df[trans_df['Type']=="OUT"]
        .sort_values(by='Date', ascending=False)
    )

with tab3:
    st.header("파주출고")
    isbn_p = st.text_input("ISBN 입력", key="p_isbn")
    qty_p  = st.number_input("수량", value=1, min_value=1, step=1, key="p_qty")
    if st.button("파주출고"):
        if isbn_p not in inv_df.index:
            st.error("등록되지 않은 ISBN")
        elif inv_df.at[isbn_p,'qty'] < qty_p:
            st.error("재고 부족")
        else:
            inv_df.at[isbn_p,'qty'] -= qty_p
            save_inventory(inv_df)
            log_transaction(isbn_p, inv_df.at[isbn_p,'Title'], -qty_p, "OUT-PAJU")
            st.success("파주출고 완료")
    st.subheader("파주출고 요약")
    st.dataframe(load_paju_summary())

with tab4:
    st.header("현재고")
    st.dataframe(
        inv_df
        .reset_index()
        .rename(columns={'qty':'수량','price':'단가','Title':'제목','author':'저자'})
    )
