import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, timedelta
import os
import json
import gspread
from google.oauth2.service_account import Credentials

# --- 1. SETUP & THEME ---
st.set_page_config(
    page_title="Smart Extemp Inventory - Sri Sangwan Sukhothai Hospital", 
    layout="wide", 
    page_icon="🏥"
)

# 🎨 CSS: ตกแต่ง UI แบบจัดเต็ม
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Prompt:wght@300;400;500;700&display=swap');
    
    p, div, input, button, select, h1, h2, h3, h4, h5, h6, table, th, td, label {
        font-family: 'Prompt', sans-serif !important;
    }
    
    /* แก้ปัญหาหัวตารางซ้อนกัน */
    .stDataTable th [data-testid="stTableColumnHeaderContent"] { padding-right: 25px !important; }
    
    /* สีพื้นหลัง Sidebar */
    [data-testid="stSidebar"] { background-color: #F2FBF2 !important; }
    
    /* ตกแต่งป้าย Tag หน่วยงาน */
    span[data-baseweb="tag"] {
        background-color: #B5EAD7 !important;
        color: #2E8B57 !important;
        font-weight: 500 !important;
        border: 1px solid #92D3BE !important;
    }
    
    /* ตกแต่งปุ่มกด */
    .stButton>button { 
        background-color: #77DD77; color: white; border-radius: 10px; border: none; 
        font-size: 16px !important; font-weight: bold !important; transition: 0.3s;
    }
    .stButton>button:hover { background-color: #4CAF50 !important; color: white !important; }

    /* กล่องแจ้งเตือน */
    .alert-box { padding: 12px; border-radius: 8px; margin-bottom: 8px; border-left: 6px solid; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. CONNECT TO GOOGLE SHEETS ---
SHEET_ID = "1_fd62tPsJRUONdRYlQ9hX9SOb-hPs7RCoxseK2onzYI" 
scopes = ["https://www.googleapis.com/auth/spreadsheets"]

try:
    if "GOOGLE_CREDENTIALS" in st.secrets:
        creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    else:
        creds = Credentials.from_service_account_file("key.json", scopes=scopes)
        
    client = gspread.authorize(creds)
    gsheet = client.open_by_key(SHEET_ID)
except Exception as e:
    st.error(f"❌ เชื่อมต่อ Google Sheets ไม่สำเร็จ: {e}")

# --- 3. HELPER FUNCTIONS ---
def safe_fmt(d):
    if pd.isna(d) or str(d) in ['NaT', 'None', '']: return "ไม่ได้ระบุ"
    try: return pd.to_datetime(d).strftime('%d/%m/%Y')
    except: return str(d).split()[0]

def load_data():
    def get_sheet_df(tab_name):
        try:
            worksheet = gsheet.worksheet(tab_name)
            values = worksheet.get_all_values() 
            if not values: return pd.DataFrame()
            return pd.DataFrame(values[1:], columns=values[0])
        except: return pd.DataFrame() 
    return get_sheet_df("Drugs"), get_sheet_df("Stock"), get_sheet_df("Locations"), get_sheet_df("CONFIG")

def save_data(df, file_name):
    file_key = file_name.replace('.csv', '').upper()
    tab_name = 'Stock' if 'STOCK' in file_key else ('Drugs' if 'DRUG' in file_key else 'Locations')
    try:
        worksheet = gsheet.worksheet(tab_name)
        worksheet.clear()
        df_safe = df.astype(str).replace(['nan', 'NaT', 'None'], '')
        data_to_upload = [df_safe.columns.tolist()] + df_safe.values.tolist()
        worksheet.update(data_to_upload)
    except Exception as e:
        st.error(f"❌ บันทึกไม่สำเร็จ: {e}")

# --- 4. MAIN APPLICATION ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.markdown("<br><br>", unsafe_allow_html=True)
    _, c2, _ = st.columns([1, 2, 1])
    with c2:
        st.markdown("<h2 style='text-align:center; color:#2E8B57;'>🏥 เข้าสู่ระบบ (Login)</h2>", unsafe_allow_html=True)
        user = st.text_input("Username")
        pwd = st.text_input("Password", type="password")
        if st.button("เข้าสู่ระบบ", use_container_width=True):
            if pwd == "1234":
                st.session_state.logged_in = True; st.session_state.role = user; st.rerun()
            else: st.error("รหัสผ่านไม่ถูกต้อง")
else:
    drugs, stock, locs, config = load_data()
    today = datetime.now()
    
    # โหลดและจัดการข้อมูล
    if stock.empty:
        stock = pd.DataFrame(columns=['Date_Produced', 'Drug_Name', 'Batch_ID', 'Qty', 'Expiry_Date', 'Location', 'Status', 'Is_Saved'])
    if locs.empty:
        locs = pd.DataFrame(columns=['Location'])
    
    stock['Expiry_Date'] = pd.to_datetime(stock['Expiry_Date'], errors='coerce')
    stock['Date_Produced'] = pd.to_datetime(stock['Date_Produced'], errors='coerce') 
    stock['Days_Left'] = (stock['Expiry_Date'] - pd.Timestamp(today.date())).dt.days
    stock['Qty'] = pd.to_numeric(stock['Qty'], errors='coerce').fillna(0)
    
    if not drugs.empty:
        stock = stock.drop(columns=['Unit_Cost', 'Type', 'BUD_Thawed'], errors='ignore')
        stock = stock.merge(drugs[['Drug_Name', 'Unit_Cost', 'Type', 'BUD_Thawed']], on='Drug_Name', how='left')
        stock['Unit_Cost'] = pd.to_numeric(stock['Unit_Cost'], errors='coerce').fillna(0)
        stock['Total_Value'] = stock['Qty'] * stock['Unit_Cost']
    else:
        stock['Unit_Cost'], stock['Total_Value'], stock['Type'], stock['BUD_Thawed'] = 0, 0, 'Unknown', 0

    # --- ส่วนหัวของแอป (Header) ที่สวยงาม ---
    col_logo, col_title = st.columns([1, 6])
    with col_logo:
        st.markdown("<h1 style='font-size:75px; text-align:center; margin-top:0;'>🏥</h1>", unsafe_allow_html=True)
    with col_title:
        st.markdown("""
            <h1 style='line-height:1.1; color:#2E8B57 !important; margin-bottom:5px;'>ระบบบริหารจัดการยาเตรียมเฉพาะรายอัจฉริยะ</h1>
            <h2 style='line-height:1.1; color:#4CAF50 !important; margin-top:0;'>Smart Extemp Inventory</h2>
            <h4 style='color:#556B2F !important;'>กลุ่มงานเภสัชกรรม โรงพยาบาลศรีสังวรสุโขทัย</h4>
        """, unsafe_allow_html=True)
    st.divider()

    with st.sidebar:
        st.success(f"👤 ผู้ใช้งาน: **{st.session_state.role.upper()}**")
        if st.button("🚪 ออกจากระบบ", use_container_width=True): st.session_state.logged_in = False; st.rerun()
        st.divider()
        st.write(f"📅 วันที่: **{today.strftime('%d/%m/%Y')}**")
        active_locs = locs['Location'].unique().tolist() if not locs.empty else []
        loc_filter = st.multiselect("เลือกดูหน่วยงาน:", active_locs, default=active_locs)

    filtered = stock[stock['Location'].isin(loc_filter)].copy()
    tab1, tab2, tab3 = st.tabs(["🚨 บริการ (Service)", "📊 ผู้บริหาร (Executive)", "⚙️ หลังบ้าน (Admin)"])

    # === TAB 1: SERVICE ===
    with tab1:
        st.markdown("### 📦 ภาพรวมสต็อกยา (Inventory Overview)")
        active_stock = stock[stock['Location'] != 'Disposal']
        if not active_stock.empty:
            stock_sum = active_stock.groupby(['Drug_Name', 'Location'])['Qty'].sum().reset_index()
            c_chart = alt.Chart(stock_sum).mark_bar().encode(
                x=alt.X('Drug_Name:N', title='รายการยา', sort='-y'),
                y=alt.Y('Qty:Q', title='จำนวนรวม (ชิ้น/ขวด)'),
                color=alt.Color('Location:N', title='สถานที่เก็บ')
            ).properties(height=350)
            st.altair_chart(c_chart, use_container_width=True)
            
            with st.expander("📋 ดูรายละเอียดสต็อกยาทั้งหมด (เรียงตามวันหมดอายุ)", expanded=True):
                detail_df = active_stock[['Drug_Name', 'Batch_ID', 'Qty', 'Location', 'Expiry_Date', 'Days_Left']].copy()
                detail_df['Expiry_Date'] = detail_df['Expiry_Date'].apply(safe_fmt)
                detail_df.columns = ['ชื่อยา', 'Batch', 'จำนวน', 'สถานที่', 'วันหมดอายุ', 'เหลืออีก (วัน)']
                st.dataframe(detail_df.sort_values('เหลืออีก (วัน)'), use_container_width=True, hide_index=True)
        else:
            st.info("ไม่มีข้อมูลยาในสต็อกขณะนี้")

        st.divider()
        st.markdown("### ⚠️ แจ้งเตือนยาใกล้หมดอายุ (Traffic Light Monitor)")
        if not filtered.empty:
            alerts = filtered[(filtered['Days_Left'] <= 7) & (filtered['Location'] != 'Disposal')].sort_values('Days_Left')
            if not alerts.empty:
                for _, r in alerts.iterrows():
                    c = "#FFCDD2" if r['Days_Left'] <= 3 else "#FFF9C4"
                    t = "#B71C1C" if r['Days_Left'] <= 3 else "#F57F17"
                    hint = " <span style='color:#D32F2F; font-weight:bold;'>(ลืมกดละลายยา?)</span>" if r['Days_Left'] < 0 and r['Status'] == 'Frozen' else ""
                    st.markdown(f"<div class='alert-box' style='background-color:{c}; border-color:{t}; color:{t};'><b>{r['Drug_Name']}</b> (Batch: {r['Batch_ID']}) - เหลือ <b>{r['Days_Left']} วัน</b> 📍 สถานที่: {r['Location']}{hint}</div>", unsafe_allow_html=True)
            else:
                st.success("✅ ยอดเยี่ยม! ไม่มียาใกล้หมดอายุในช่วง 7 วันนี้")
        else:
            st.success("✅ ไม่มียาในระบบ")

        st.divider()
        c_th, c_di, c_wa = st.columns(3)
        
        with c_th:
            st.markdown("#### ❄️ แจ้งเตือนละลายยา")
            if 'Type' in filtered.columns and not filtered.empty:
                f_items = filtered[(filtered['Type'] == 'Frozen') & (filtered['Status'] == 'Frozen')]
                
                f_alerts = f_items[f_items['Days_Left'] <= 3].sort_values('Days_Left')
                if not f_alerts.empty:
                    for _, r in f_alerts.iterrows():
                        if r['Days_Left'] < 0:
                            st.markdown(f"<div style='color:#D32F2F; font-size:14px; font-weight:bold;'>❌ เลยกำหนด: {r['Drug_Name']}</div>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"<div style='color:#F57C00; font-size:14px; font-weight:bold;'>⚠️ เหลือ {r['Days_Left']} วัน: {r['Drug_Name']}</div>", unsafe_allow_html=True)
                
                if not f_items.empty:
                    thaw_sel = st.selectbox("เลือกยาที่ต้องการละลาย:", f_items.apply(lambda x: f"{x['Drug_Name']} (Batch: {x['Batch_ID']})", axis=1), index=None, key="thaw_sel")
                    if thaw_sel:
                        t_bid = thaw_sel.split("Batch: ")[1].split(")")[0]
                        if st.button("💧 ยืนยันละลายยา", type="primary", use_container_width=True):
                            t_row = stock[stock['Batch_ID']==t_bid].iloc[0]
                            bud = int(t_row['BUD_Thawed']) if str(t_row['BUD_Thawed']).isdigit() else 0
                            stock.loc[stock['Batch_ID']==t_bid, ['Status', 'Expiry_Date']] = ['Thawed', today + timedelta(days=bud)]
                            save_data(stock, 'stock'); st.success("ละลายยาสำเร็จ!"); st.rerun()
                else: st.info("ไม่มียาแช่แข็งรอละลาย")
            else: st.info("ไม่มียาแช่แข็งในระบบ")

        with c_di:
            st.markdown("#### ✂️ ตัดจ่ายยาปกติ")
            d_l = st.selectbox("จ่ายจากห้อง:", active_locs, index=None, placeholder="-- เลือกห้อง --", key="d_l")
            if d_l:
                d_items = stock[stock['Location'] == d_l]
                if not d_items.empty:
                    d_sel = st.selectbox("เลือกยา:", d_items.apply(lambda x: f"{x['Drug_Name']} (Batch: {x['Batch_ID']}) [เหลือ {int(x['Qty'])}]", axis=1), index=None)
                    if d_sel:
                        bid = d_sel.split("Batch: ")[1].split(")")[0]
                        max_q = int(stock.loc[stock['Batch_ID']==bid, 'Qty'].values[0])
                        q_cut = st.number_input("จำนวนจ่าย:", 1, max_q, max_q)
                        if st.button("✅ ยืนยันจ่ายยา", use_container_width=True):
                            if max_q - q_cut <= 0: stock = stock[stock['Batch_ID']!=bid]
                            else: stock.loc[stock['Batch_ID']==bid, 'Qty'] = max_q - q_cut
                            save_data(stock, 'stock'); st.success("จ่ายยาสำเร็จ!"); st.rerun()
                else: st.warning("ไม่มีรายการยาในห้องนี้")

        with c_wa:
            st.markdown("#### 🗑️ ตัดยาทิ้ง/หมดอายุ")
            w_l = st.selectbox("ทิ้งจากห้อง:", active_locs, index=None, placeholder="-- เลือกห้อง --", key="w_l")
            if w_l:
                w_items = stock[stock['Location'] == w_l]
                if not w_items.empty:
                    w_sel = st.selectbox("เลือกยาที่ทิ้ง:", w_items.apply(lambda x: f"{x['Drug_Name']} (Batch: {x['Batch_ID']}) [เหลือ {int(x['Qty'])}]", axis=1), index=None)
                    if w_sel:
                        wbid = w_sel.split("Batch: ")[1].split(")")[0]
                        wmax = int(stock.loc[stock['Batch_ID']==wbid, 'Qty'].values[0])
                        q_w = st.number_input("จำนวนทิ้ง:", 1, wmax, wmax)
                        if st.button("🗑️ ยืนยันการทิ้ง", type="primary", use_container_width=True):
                            if wmax - q_w <= 0: stock.loc[stock['Batch_ID']==wbid, 'Location'] = 'Disposal'
                            else:
                                stock.loc[stock['Batch_ID']==wbid, 'Qty'] = wmax - q_w
                                new_w = stock[stock['Batch_ID']==wbid].iloc[0].copy()
                                new_w['Qty'] = q_w; new_w['Location'] = 'Disposal'
                                stock = pd.concat([stock, pd.DataFrame([new_w])], ignore_index=True)
                            save_data(stock, 'stock'); st.error("บันทึกการทิ้งสำเร็จ"); st.rerun()

    # === TAB 2: EXECUTIVE ===
    with tab2:
        st.markdown("### 💰 สรุปรายงานมูลค่าทางการเงิน")
        c1, c2 = st.columns(2)
        sd = c1.date_input("ตั้งแต่วันที่:", today.date() - timedelta(days=30))
        ed = c2.date_input("ถึงวันที่:", today.date())
        
        if not stock.empty:
            st_date = pd.to_datetime(stock['Date_Produced'], errors='coerce')
            mask = (st_date.dt.date >= sd) & (st_date.dt.date <= ed)
            t2_stock = stock[mask].copy()
            
            if not t2_stock.empty:
                v_total = t2_stock[t2_stock['Location'] != 'Disposal']['Total_Value'].sum()
                v_waste = t2_stock[t2_stock['Location'] == 'Disposal']['Total_Value'].sum()
                m1, m2 = st.columns(2)
                m1.metric("📦 มูลค่าคงคลังรับเข้าทั้งหมด", f"{v_total:,.2f} บาท")
                m2.metric("🗑️ มูลค่าความสูญเสีย (Waste)", f"{v_waste:,.2f} บาท", delta="- จากยาหมดอายุ/ชำรุด", delta_color="inverse")
            else:
                st.info("ไม่มีข้อมูลรับเข้ายาในช่วงเวลาที่เลือก")

    # === TAB 3: ADMIN ===
    with tab3:
        if st.session_state.role == 'admin':
            adm_t1, adm_t2 = st.tabs(["📥 ฟอร์มรับยาเข้า", "🛠️ แก้ไขฐานข้อมูล (Database)"])
            with adm_t1:
                with st.form("in_form", clear_on_submit=True):
                    st.markdown("#### 📝 บันทึกรับยาเข้า (New Stock)")
                    c1, c2 = st.columns(2)
                    drug_list = drugs['Drug_Name'].unique() if not drugs.empty else []
                    dn = c1.selectbox("ชื่อยา:", drug_list, index=None, placeholder="-- เลือกยา --")
                    bn = c1.text_input("เลข Batch:")
                    qn = c2.number_input("จำนวนรับเข้า:", min_value=1)
                    pn = c2.date_input("วันที่ผลิต:", today)
                    ln = c2.selectbox("สถานที่เก็บ:", active_locs, index=None, placeholder="-- เลือกห้อง --")
                    
                    if st.form_submit_button("✅ บันทึกรับเข้าสต็อก", use_container_width=True):
                        if dn and bn and ln:
                            dinfo = drugs[drugs['Drug_Name']==dn].iloc[0]
                            bud = dinfo['BUD_Frozen'] if dinfo['Type']=='Frozen' else (dinfo['BUD_Thawed'] if dinfo['Type']=='Cold' else dinfo['BUD_Room'])
                            days = int(float(bud)) if str(bud).strip() != "" else 0
                            en = pn + timedelta(days=days)
                            new_r = {
                                'Date_Produced': pn.strftime('%Y-%m-%d'), 'Drug_Name': dn, 'Batch_ID': bn,
                                'Qty': qn, 'Expiry_Date': en.strftime('%Y-%m-%d'), 'Location': ln,
                                'Status': 'Frozen' if dinfo['Type'] == 'Frozen' else 'Active', 'Is_Saved': 'FALSE'
                            }
                            stock = pd.concat([stock, pd.DataFrame([new_r])], ignore_index=True)
                            save_data(stock, 'stock'); st.success("บันทึกรับเข้าสำเร็จ!"); st.rerun()
                        else:
                            st.error("⚠️ กรุณากรอกข้อมูลให้ครบถ้วนก่อนบันทึก")
            with adm_t2:
                st.markdown("#### 🛠️ แก้ไขข้อมูลสต็อกดิบ (Raw Data)")
                st.warning("⚠️ การแก้ไขข้อมูลในหน้านี้จะส่งผลโดยตรงต่อระบบ กรุณาตรวจสอบให้แน่ใจก่อนกดบันทึก")
                ed_s = st.data_editor(stock.drop(columns=['Days_Left','Total_Value','BUD_Thawed','Type'], errors='ignore'), num_rows="dynamic", use_container_width=True)
                if st.button("💾 ยืนยันการแก้ไขลง Cloud", use_container_width=True): save_data(ed_s, 'stock'); st.success("อัปเดตข้อมูลเรียบร้อย"); st.rerun()
