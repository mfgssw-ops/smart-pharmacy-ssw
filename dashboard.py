import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, timedelta
import calendar
import gspread
from google.oauth2.service_account import Credentials
import re
import json
import os

# --- 1. SETUP & THEME ---
st.set_page_config(page_title="Smart Extemp Inventory - SSW Hospital", layout="wide", page_icon="SSW_Logo.jpg")

# 🎨 CSS: ตกแต่ง UI
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Sarabun:wght@400;500;700&family=Prompt:wght@400;500;700&display=swap');
    h1, h2, h3, h4, h5, h6, p, div, span, label, button, li, input, select, td, th { font-family: 'Sarabun', 'Prompt', sans-serif; }
    .material-symbols-rounded, .material-icons, [class*="icon"] { font-family: 'Material Symbols Rounded', 'Material Icons', sans-serif !important; }
    .block-container { padding-top: 3.5rem !important; padding-bottom: 1rem !important; }
    .header-container { display: flex; align-items: center; justify-content: center; gap: 15px; margin-bottom: 5px; }
    .header-logo { width: 85px !important; }
    .header-title { color: #2E8B57 !important; font-size: 34px !important; font-weight: bold !important; margin: 0; }
    .custom-header { color: #1E5631; font-size: 22px; font-weight: 700; margin-top: 25px; margin-bottom: 15px; border-bottom: 2px solid #A8E6CF; padding-bottom: 8px; }
    .custom-subheader { color: #2E8B57; font-size: 18px; font-weight: 700; margin-top: 10px; margin-bottom: 15px; }
    div[data-testid="stButton"] button { background-color: #77DD77 !important; color: white !important; border-radius: 10px !important; font-size: 18px !important; font-weight: bold !important; border: none !important; padding: 10px 20px !important; transition: 0.3s; }
    div[data-testid="stButton"] button:hover { background-color: #5bbd5b !important; color: white !important; border: 1px solid #ffffff !important; }
    .stCheckbox label p { color: #1E5631 !important; font-weight: 500 !important; font-size: 16px !important; }
    .stTabs [data-baseweb="tab-list"] button { background-color: #f0f2f6; border-radius: 10px 10px 0px 0px; padding: 10px 20px; font-size: 18px !important; font-weight: bold !important; }
    .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] { background-color: #2E8B57 !important; color: white !important; }
    .alert-box { padding: 12px; border-radius: 8px; margin-bottom: 8px; border-left: 6px solid; font-size: 16px; }
    .stCheckbox { margin-top: -10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. CONNECT TO GOOGLE SHEETS ---
SHEET_ID = "1_fd62tPsJRUONdRYlQ9hX9SOb-hPs7RCoxseK2onzYI" 
scopes = ["https://www.googleapis.com/auth/spreadsheets"]

@st.cache_resource
def get_gsheet_client():
    if os.path.exists("service_account.json"):
        try: return gspread.authorize(Credentials.from_service_account_file("service_account.json", scopes=scopes))
        except: pass
    try:
        if "google_credentials" in st.secrets:
            creds_info = json.loads(st.secrets["google_credentials"])
            return gspread.authorize(Credentials.from_service_account_info(creds_info, scopes=scopes))
    except: pass
    return None

client = get_gsheet_client()

# --- 3. DATA FUNCTIONS ---
def safe_fmt(d):
    if pd.isna(d) or str(d) in ['NaT', 'None', '']: return "ไม่ได้ระบุ"
    try: return pd.to_datetime(d).strftime('%d/%m/%Y')
    except: return str(d).split()[0]

@st.cache_data(ttl=60, show_spinner=False)
def load_data():
    if not client: return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    try:
        gsheet = client.open_by_key(SHEET_ID)
        def get_df(name):
            try:
                values = gsheet.worksheet(name).get_all_values()
                df = pd.DataFrame(values[1:], columns=values[0]) if values else pd.DataFrame()
                df.columns = df.columns.astype(str).str.strip()
                return df
            except: return pd.DataFrame()
            
        d_df = get_df("Drugs")
        s_df = get_df("Stock")
        l_df = get_df("Locations")
        u_df = get_df("Users")
        
        if u_df.empty: st.cache_data.clear()
        return d_df, s_df, l_df, u_df
    except Exception: 
        st.cache_data.clear()
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

def save_data(df, file_name):
    if df is None: return
    tab_name = 'Stock' if 'stock' in file_name.lower() else ('Drugs' if 'drug' in file_name.lower() else 'Locations')
    df_clean = df.copy()
    
    if tab_name == 'Stock':
        cols_to_drop = ['Days_Left', 'Total_Value', 'Unit_Cost', 'Type', 'BUD_Cold', 'merge_key']
        df_clean = df_clean.drop(columns=[c for c in cols_to_drop if c in df_clean.columns], errors='ignore')
        for col in ['Date_Produced', 'Expiry_Date']:
            if col in df_clean.columns:
                df_clean[col] = pd.to_datetime(df_clean[col], errors='coerce').dt.strftime('%Y-%m-%d').fillna('')
                
    try:
        df_safe = df_clean.astype(str).replace(['nan', 'NaT', 'None', '<NA>'], '')
        data_to_upload = [df_safe.columns.tolist()] + df_safe.values.tolist()
        worksheet = client.open_by_key(SHEET_ID).worksheet(tab_name)
        worksheet.clear()
        worksheet.update(data_to_upload)
        load_data.clear() 
    except Exception as e: st.error(f"❌ บันทึกไม่สำเร็จ: {e}")

drugs, stock, locs, users_df = load_data()

# --- 4. MAIN APP ROUTING ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False

if not st.session_state.logged_in:
    _, c2, _ = st.columns([1, 2, 1])
    with c2:
        st.markdown(f"""
            <div class="header-container">
                <img src="https://raw.githubusercontent.com/mfgssw-ops/smart-pharmacy-ssw/main/SSW_Logo.jpg" class="header-logo">
                <h1 class="header-title">Smart Extemp Inventory</h1>
            </div>
            <p style='text-align:center; color:#666; 'font-weight: bold; font-size:18px; margin-top:-5px; margin-bottom:30px;'>กลุ่มงานเภสัชกรรม โรงพยาบาลศรีสังวรสุโขทัย</p>
        """, unsafe_allow_html=True)
        
        if client is None: st.error("⚠️ ไม่พบไฟล์เชื่อมต่อฐานข้อมูล")
        
        u = st.text_input("ชื่อผู้ใช้งาน (Username)", placeholder="ระบุ Username")
        p = st.text_input("รหัสผ่าน (Password)", type="password", placeholder="ระบุ Password")
        st.markdown("<br>", unsafe_allow_html=True) 
        
        if st.button("เข้าสู่ระบบ", use_container_width=True):
            if client and not users_df.empty:
                match = users_df[(users_df['Username'].astype(str) == u.strip()) & (users_df['Password'].astype(str) == p.strip())]
                if not match.empty:
                    st.session_state.logged_in = True
                    st.session_state.user_name = match.iloc[0]['Name']
                    st.session_state.role = match.iloc[0].get('Role', 'staff').lower()
                    st.rerun()
                else: st.error("❌ ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
            else: st.warning("⚠️ ไม่สามารถเชื่อมต่อฐานข้อมูลผู้ใช้ได้ (กรุณากด Clear Cache ที่มุมขวาบน)")
else:
    today = datetime.now()
    if not stock.empty:
        # 💡 สร้างระบบเก็บประวัติการทำงาน (Record Status) 💡
        if 'Record_Status' not in stock.columns:
            stock['Record_Status'] = 'In_Stock'
            # แก้ไขข้อมูลเก่าให้เข้ากับระบบใหม่
            stock.loc[stock['Location'] == 'Disposal', 'Record_Status'] = 'Disposed'
            
        for c in ['Date_Produced', 'Expiry_Date']:
            if c not in stock.columns: stock[c] = ''
            
        stock['Qty'] = pd.to_numeric(stock['Qty'], errors='coerce').fillna(0)
        stock['Date_Produced'] = pd.to_datetime(stock['Date_Produced'], errors='coerce') 
        stock['Expiry_Date'] = pd.to_datetime(stock['Expiry_Date'], errors='coerce')
        stock['Days_Left'] = (stock['Expiry_Date'] - pd.Timestamp(today.date())).dt.days
        
        if 'Status' not in stock.columns: stock['Status'] = 'Active'
        if 'Action_By' not in stock.columns: stock['Action_By'] = '-'
        
        if not drugs.empty:
            stock['merge_key'] = stock['Drug_Name'].astype(str).str.replace(r'\s+', '', regex=True).str.lower()
            drugs_m = drugs.copy()
            drugs_m['merge_key'] = drugs_m['Drug_Name'].astype(str).str.replace(r'\s+', '', regex=True).str.lower()
            u_cost_col = next((c for c in drugs_m.columns if 'cost' in str(c).lower() or 'ราคา' in str(c)), None)
            type_col = next((c for c in drugs_m.columns if 'type' in str(c).lower() or 'ประเภท' in str(c)), None)
            bud_col = next((c for c in drugs_m.columns if 'cold' in str(c).lower()), None)
            
            cols_to_merge = ['merge_key']
            if u_cost_col: cols_to_merge.append(u_cost_col)
            if type_col: cols_to_merge.append(type_col)
            if bud_col: cols_to_merge.append(bud_col)
            stock = stock.merge(drugs_m[cols_to_merge], on='merge_key', how='left')
            
            rename_dict = {}
            if u_cost_col: rename_dict[u_cost_col] = 'Unit_Cost'
            if type_col: rename_dict[type_col] = 'Type'
            if bud_col: rename_dict[bud_col] = 'BUD_Cold'
            stock = stock.rename(columns=rename_dict)
        
        if 'Unit_Cost' not in stock.columns: stock['Unit_Cost'] = 0
        if 'Type' not in stock.columns: stock['Type'] = 'Room'
        stock['Unit_Cost'] = pd.to_numeric(stock['Unit_Cost'].astype(str).replace(r'[^\d.]', '', regex=True), errors='coerce').fillna(0)
        stock['Total_Value'] = stock['Qty'] * stock['Unit_Cost']

    with st.sidebar:
        st.markdown("""
            <div style="text-align: center; margin-bottom: 20px;">
                <img src="https://raw.githubusercontent.com/mfgssw-ops/smart-pharmacy-ssw/main/SSW_Logo.jpg" width="80" style="border-radius: 10px;">
            </div>
        """, unsafe_allow_html=True)
        st.success(f"👤 คุณ {st.session_state.user_name}\n\n🔑 สิทธิ์: {st.session_state.role.upper()}")
        st.markdown("<p style='font-weight: bold; font-size: 16px; margin-bottom: 10px; color:#2E8B57;'>📍 เลือกหน่วยงานที่ต้องการดู:</p>", unsafe_allow_html=True)
        
        active_locs = locs['Location'].unique().tolist() if not locs.empty else []
        selected_wards = []
        if active_locs:
            for ward in active_locs:
                if st.checkbox(ward, value=True, key=f"cb_{ward}"):
                    selected_wards.append(ward)
        else:
            st.info("ไม่มีข้อมูลหน่วยงาน")
            
        st.markdown("<hr style='margin-top: 10px; margin-bottom: 15px;'>", unsafe_allow_html=True)
        if st.button("🚪 ออกจากระบบ", use_container_width=True): 
            st.session_state.logged_in = False
            st.rerun()

    st.markdown('<h1 style="color:#2E8B57;">Smart Extemp Inventory</h1><p style="color:#666; font-size:18px;">ระบบบริหารจัดการยาเตรียมเฉพาะราย กลุ่มงานเภสัชกรรม โรงพยาบาลศรีสังวรสุโขทัย</p>', unsafe_allow_html=True)

    if not selected_wards:
        st.warning("⚠️ กรุณาติ๊กเลือกหน่วยงานที่แถบด้านซ้ายอย่างน้อย 1 แห่ง เพื่อแสดงข้อมูลค่ะ")
    else:
        # กรองข้อมูลตามวอร์ดที่เลือก
        filtered = stock[stock['Location'].isin(selected_wards)].copy()
        tab1, tab2, tab3 = st.tabs(["🚨 บริการ (Service)", "📊 ผู้บริหาร (Executive)", "⚙️ หลังบ้าน (Admin)"])

        with tab1:
            st.markdown("<div class='custom-header'>⚠️ การแจ้งเตือน (Alerts)</div>", unsafe_allow_html=True)
            col_alert1, col_alert2 = st.columns(2)
            
            # โชว์เฉพาะยาที่ยังมีในตู้ (In_Stock)
            with col_alert1:
                st.markdown("<div class='custom-subheader'>📅 แจ้งเตือนยาหมดอายุ (ภายใน 10 วัน)</div>", unsafe_allow_html=True)
                alerts = filtered[(filtered['Days_Left'] <= 10) & (filtered['Record_Status'] == 'In_Stock')].sort_values('Days_Left')
                if alerts.empty: st.success("✅ ไม่มียาใกล้หมดอายุใน 10 วันนี้")
                
                for _, r in alerts.iterrows():
                    c = "#FFCDD2" if r['Days_Left'] <= 7 else "#FFF9C4"
                    st.markdown(f"<div class='alert-box' style='background-color:{c};'><b>{r['Drug_Name']}</b> ({r['Batch_ID']}) - เหลือ {int(r['Days_Left'])} วัน 📍 {r['Location']}</div>", unsafe_allow_html=True)

            with col_alert2:
                st.markdown("<div class='custom-subheader'>❄️ เตือนละลายยา (Frozen -> Cold)</div>", unsafe_allow_html=True)
                if 'Type' in filtered.columns:
                    f_items = filtered[(filtered['Type'] == 'Frozen') & (filtered['Status'] == 'Frozen') & (filtered['Record_Status'] == 'In_Stock')]
                    if f_items.empty: st.success("✅ ไม่มีรายการยาแช่แข็งที่ต้องละลาย")
                    for idx, r in f_items.iterrows():
                        if st.button(f"💧 นำออกตู้แช่: {r['Drug_Name']} ({r['Batch_ID']})", key=f"thaw_{r['Batch_ID']}"):
                            match = re.search(r'\d+', str(r.get('BUD_Cold', 0)))
                            bud = int(match.group()) if match else 7 
                            new_exp = today + timedelta(days=bud)
                            # อัปเดตผ่าน Index เพื่อความปลอดภัย
                            stock.loc[idx, ['Status', 'Expiry_Date', 'Action_By']] = ['Thawed', new_exp.strftime('%Y-%m-%d'), st.session_state.user_name]
                            save_data(stock, 'stock'); st.success(f"คำนวณวันหมดอายุใหม่สำเร็จ!"); st.rerun()

            st.markdown("<div class='custom-header'>📦 ภาพรวมสต็อกยาปัจจุบัน</div>", unsafe_allow_html=True)
            active_stock = filtered[filtered['Record_Status'] == 'In_Stock']
            if not active_stock.empty:
                chart_data = active_stock.groupby(['Drug_Name', 'Location'])['Qty'].sum().reset_index()
                c_chart = alt.Chart(chart_data).mark_bar().encode(
                    x=alt.X('Drug_Name:N', title='รายการยา', sort='-y'),
                    y=alt.Y('Qty:Q', title='จำนวน'),
                    color=alt.Color('Location:N', scale=alt.Scale(scheme='pastel1')),
                    tooltip=['Drug_Name', 'Location', 'Qty']
                ).properties(height=280)
                st.altair_chart(c_chart, use_container_width=True)
                
                with st.expander("🔍 คลิกเพื่อดูรายละเอียดสต็อกยาเรียงตามวันหมดอายุ"):
                    detail_df = active_stock[['Drug_Name', 'Batch_ID', 'Qty', 'Location', 'Status', 'Expiry_Date', 'Days_Left', 'Action_By']].copy()
                    detail_df['Expiry_Date'] = detail_df['Expiry_Date'].apply(safe_fmt)
                    st.dataframe(detail_df.sort_values('Days_Left'), use_container_width=True, hide_index=True)

            st.markdown("<div class='custom-header'>🛠️ ระบบจัดการยา (Operations)</div>", unsafe_allow_html=True)
            c_op1, c_op2, c_op3 = st.columns(3)
            
            # 💡 ระบบการดำเนินการจะดึงเฉพาะยาที่ In_Stock เท่านั้น
            valid_stock = stock[stock['Record_Status'] == 'In_Stock']
            
            with c_op1:
                st.markdown("<div class='custom-subheader'>✂️ ตัดจ่ายปกติ (FEFO)</div>", unsafe_allow_html=True)
                d_l = st.selectbox("จ่ายจากหน่วยงาน:", selected_wards, index=None, placeholder="-- เลือกหน่วย --", key="dl")
                if d_l:
                    d_items = valid_stock[(valid_stock['Location'] == d_l) & (valid_stock['Qty'] > 0)]
                    if not d_items.empty:
                        drug_summary = d_items.groupby('Drug_Name')['Qty'].sum().reset_index()
                        d_sel = st.selectbox("เลือกชื่อยา:", drug_summary.apply(lambda x: f"{x['Drug_Name']} [รวม {int(x['Qty'])}]", axis=1), index=None)
                        if d_sel:
                            selected_drug = d_sel.split(" [")[0]
                            max_q = int(drug_summary[drug_summary['Drug_Name'] == selected_drug]['Qty'].values[0])
                            
                            q_cut = st.number_input("จำนวนที่ต้องการจ่าย:", 1, max_q, max_q)
                            if st.button("✅ ยืนยันจ่ายยา"):
                                target_batches = d_items[d_items['Drug_Name'] == selected_drug].sort_values('Expiry_Date', na_position='last')
                                remain_to_cut = q_cut
                                
                                for idx, row in target_batches.iterrows():
                                    if remain_to_cut <= 0: break
                                    batch_qty = row['Qty']
                                    
                                    if batch_qty <= remain_to_cut:
                                        # 💡 เปลี่ยนเป็น 'Dispensed' โดยไม่ลบจำนวนทิ้ง เพื่อเก็บมูลค่าประหยัด
                                        remain_to_cut -= batch_qty
                                        stock.loc[idx, 'Record_Status'] = 'Dispensed'
                                        stock.loc[idx, 'Action_By'] = f"จ่ายยาให้ผู้ป่วย ({st.session_state.user_name})"
                                    else:
                                        # หักลบส่วนที่เหลือ และแยกบรรทัดใหม่ไปไว้ในหมวด Dispensed
                                        stock.loc[idx, 'Qty'] = batch_qty - remain_to_cut
                                        stock.loc[idx, 'Action_By'] = f"จ่ายยาให้ผู้ป่วย ({st.session_state.user_name})"
                                        
                                        new_dispensed = stock.loc[idx].copy()
                                        new_dispensed['Qty'] = remain_to_cut
                                        new_dispensed['Record_Status'] = 'Dispensed'
                                        stock = pd.concat([stock, pd.DataFrame([new_dispensed])], ignore_index=True)
                                        remain_to_cut = 0
                                        
                                save_data(stock, 'stock')
                                st.success(f"จ่าย {selected_drug} สำเร็จ! (ระบบตัดล็อตที่หมดอายุก่อนให้แล้ว)")
                                st.rerun()
                    else:
                        st.info("ไม่มียาคงคลังในหน่วยงานนี้")

            with c_op2:
                st.markdown("<div class='custom-subheader'>🔄 ช่วยกันใช้ (โอนยา)</div>", unsafe_allow_html=True)
                t_from = st.selectbox("ต้นทาง:", selected_wards, index=None, placeholder="-- โอนจาก --", key="tf")
                t_to = st.selectbox("ปลายทาง:", active_locs, index=None, placeholder="-- โอนไป --", key="tt")
                if t_from and t_to and t_from != t_to:
                    t_items = valid_stock[valid_stock['Location'] == t_from]
                    t_sel = st.selectbox("เลือกยาโอน:", t_items.apply(lambda x: f"{x['Drug_Name']} ({x['Batch_ID']}) [เหลือ {int(x['Qty'])}]", axis=1), index=None)
                    if t_sel:
                        tbid = t_sel.split("(")[1].split(")")[0]
                        # ค้นหา Index เพื่อป้องกันการแก้ผิดบรรทัด
                        target_idx = t_items[t_items['Batch_ID'] == tbid].index[0]
                        tmax = int(stock.loc[target_idx, 'Qty'])
                        q_t = st.number_input("จำนวนโอน:", 1, tmax, tmax)
                        if st.button("🔄 ยืนยันโอนยา"):
                            if tmax - q_t <= 0: 
                                stock.loc[target_idx, ['Location', 'Status', 'Action_By']] = [t_to, 'Transferred', st.session_state.user_name]
                            else:
                                stock.loc[target_idx, 'Qty'] = tmax - q_t
                                new_t = stock.loc[target_idx].copy()
                                new_t['Qty'] = q_t; new_t['Location'] = t_to; new_t['Status'] = 'Transferred'; new_t['Action_By'] = st.session_state.user_name
                                stock = pd.concat([stock, pd.DataFrame([new_t])], ignore_index=True)
                            save_data(stock, 'stock'); st.success(f"โอนยาสำเร็จ!"); st.rerun()

            with c_op3:
                st.markdown("<div class='custom-subheader'>🗑️ ตัดยาหมดอายุ</div>", unsafe_allow_html=True)
                w_l = st.selectbox("ทิ้งจากหน่วยงาน:", selected_wards, index=None, placeholder="-- เลือกหน่วย --", key="wl")
                if w_l:
                    w_items = valid_stock[(valid_stock['Location'] == w_l) & (valid_stock['Days_Left'] < 0)]
                    if not w_items.empty:
                        w_sel = st.selectbox("เลือกยาที่ต้องการทิ้ง:", w_items.apply(lambda x: f"{x['Drug_Name']} ({x['Batch_ID']}) [เหลือ {int(x['Qty'])}]", axis=1), index=None)
                        if w_sel:
                            wbid = w_sel.split("(")[1].split(")")[0]
                            target_idx = w_items[w_items['Batch_ID'] == wbid].index[0]
                            wmax = int(stock.loc[target_idx, 'Qty'])
                            q_w = st.number_input("จำนวนทิ้ง:", 1, wmax, wmax)
                            if st.button("🗑️ ยืนยันทิ้งยา"):
                                if wmax - q_w <= 0: 
                                    stock.loc[target_idx, ['Record_Status', 'Action_By']] = ['Disposed', f"ทิ้งโดย {st.session_state.user_name}"]
                                else:
                                    stock.loc[target_idx, 'Qty'] = wmax - q_w
                                    new_w = stock.loc[target_idx].copy()
                                    new_w['Qty'] = q_w; new_w['Record_Status'] = 'Disposed'; new_w['Action_By'] = f"ทิ้งโดย {st.session_state.user_name}"
                                    stock = pd.concat([stock, pd.DataFrame([new_w])], ignore_index=True)
                                save_data(stock, 'stock'); st.error("บันทึกการทิ้งสำเร็จ"); st.rerun()
                    else:
                        st.success("✅ ไม่มียาหมดอายุในหน่วยงานนี้")

        # === TAB 2: EXECUTIVE ===
        with tab2:
            st.markdown("<div class='custom-header'>📊 สรุปรายงานมูลค่าและการบริหารจัดการ</div>", unsafe_allow_html=True)
            st.markdown("<div class='custom-subheader'>📅 เลือกช่วงเวลาที่ต้องการดูข้อมูล (รอบวันที่รับเข้า/ผลิต)</div>", unsafe_allow_html=True)
            c_date1, c_date2 = st.columns(2)
            
            _, last_day_num = calendar.monthrange(today.year, today.month)
            default_start = today.date().replace(day=1)
            default_end = today.date().replace(day=last_day_num)
            
            start_date = c_date1.date_input("ตั้งแต่วันที่:", default_start)
            end_date = c_date2.date_input("ถึงวันที่:", default_end)
            
            if not filtered.empty:
                mask = (filtered['Date_Produced'].dt.date >= start_date) & (filtered['Date_Produced'].dt.date <= end_date)
                t2_stock = filtered[mask].copy()
                
                # คำนวณเฉพาะยาที่ In_Stock (คงคลัง)
                v_total = t2_stock[t2_stock['Record_Status'] == 'In_Stock']['Total_Value'].sum()
                # คำนวณยาที่ถูกทำลาย (Disposed)
                v_waste = t2_stock[t2_stock['Record_Status'] == 'Disposed']['Total_Value'].sum()
                # 💡 คำนวณมูลค่าประหยัด: ยาที่ถูกโอน (Transferred) และไม่ได้ถูกนำไปทิ้ง (รวมทั้งคงคลัง และจ่ายให้ผู้ป่วยแล้ว)
                v_saved = t2_stock[(t2_stock['Status'] == 'Transferred') & (t2_stock['Record_Status'].isin(['In_Stock', 'Dispensed']))]['Total_Value'].sum()

                m1, m2, m3 = st.columns(3)
                m1.metric("📦 มูลค่ายาคงคลัง (ในตู้)", f"฿ {v_total:,.2f}")
                m2.metric("♻️ มูลค่าประหยัดได้ (ช่วยกันใช้)", f"฿ {v_saved:,.2f}")
                m3.metric("🗑️ มูลค่าสูญเสีย (ทิ้ง/หมดอายุ)", f"฿ {v_waste:,.2f}", delta_color="inverse")
                st.markdown("<br>", unsafe_allow_html=True)
                
                with st.expander("🗑️ คลิกดูรายละเอียด 'ยาที่สูญเสีย/หมดอายุ' (ใช้พิจารณาลดการสำรอง)"):
                    df_waste = t2_stock[t2_stock['Record_Status'] == 'Disposed'].copy()
                    if not df_waste.empty:
                        df_waste['หมายเหตุ'] = df_waste['Status'].apply(
                            lambda x: "⚠️ โอนช่วยใช้แล้ว แต่ก็ยังหมดอายุ" if x == 'Transferred' else "ทิ้ง/หมดอายุ ปกติ"
                        )
                        df_waste['วันที่รับเข้า'] = df_waste['Date_Produced'].dt.strftime('%d/%m/%Y')
                        show_waste_cols = ['วันที่รับเข้า', 'Drug_Name', 'Batch_ID', 'Qty', 'Location', 'Total_Value', 'หมายเหตุ', 'Action_By']
                        st.dataframe(df_waste[show_waste_cols].style.format({'Total_Value': '{:,.2f}'}), use_container_width=True, hide_index=True)
                    else:
                        st.success("🎉 ไม่มียาที่สูญเสียในช่วงเวลานี้")
                        
                with st.expander("📦 คลิกดูรายละเอียด 'ยาคงคลัง' และ 'ยาที่จ่ายให้ผู้ป่วยแล้ว (ประหยัดสำเร็จ)'"):
                    df_active = t2_stock[t2_stock['Record_Status'].isin(['In_Stock', 'Dispensed'])].copy()
                    if not df_active.empty:
                        df_active['สถานะยา'] = df_active['Record_Status'].map({'In_Stock':'📦 คงคลัง', 'Dispensed':'✅ จ่ายแล้ว'})
                        df_active['ประวัติ'] = df_active['Status'].apply(lambda x: "♻️ รับโอนมา" if x == 'Transferred' else "-")
                        df_active['วันที่รับเข้า'] = df_active['Date_Produced'].dt.strftime('%d/%m/%Y')
                        show_active_cols = ['วันที่รับเข้า', 'Drug_Name', 'Batch_ID', 'Qty', 'Location', 'สถานะยา', 'ประวัติ', 'Total_Value']
                        st.dataframe(df_active[show_active_cols].style.format({'Total_Value': '{:,.2f}'}), use_container_width=True, hide_index=True)
                    else:
                        st.info("ไม่มีรายการยาคงคลังหรือเบิกจ่ายในรอบเวลานี้")
            else:
                st.info("ไม่พบข้อมูลในหน่วยงานที่เลือก")

        with tab3:
            if st.session_state.role == 'admin':
                adm_t1, adm_t2, adm_t3 = st.tabs(["📥 รับยาเข้า", "🛠️ แก้ไขสต็อก", "💊 ฐานข้อมูลยา (Master Data)"])
                with adm_t1:
                    with st.form("in_form", clear_on_submit=True):
                        c1, c2 = st.columns(2)
                        dn = c1.selectbox("ชื่อยา:", drugs['Drug_Name'].unique() if not drugs.empty else [], index=None)
                        bn = c1.text_input("Batch ID:")
                        qn = c2.number_input("จำนวน:", min_value=1)
                        pn = c2.date_input("วันผลิต/รับเข้า:", today)
                        ln = c2.selectbox("ห้องเก็บ:", active_locs, index=None)
                        if st.form_submit_button("บันทึกรับเข้า"):
                            if dn and bn and ln:
                                dinfo = drugs[drugs['Drug_Name']==dn].iloc[0]
                                dtype = str(dinfo.get('Type', 'Room')).strip()
                                bud_val = dinfo.get('BUD_Frozen', 0) if dtype == 'Frozen' else (dinfo.get('BUD_Cold', 0) if dtype == 'Cold' else dinfo.get('BUD_Room', 0))
                                match = re.search(r'\d+', str(bud_val))
                                days = int(match.group()) if match else 30
                                en = pn + timedelta(days=days)
                                
                                new_r = {
                                    'Date_Produced': pn.strftime('%Y-%m-%d'), 'Drug_Name': dn, 'Batch_ID': bn,
                                    'Qty': qn, 'Expiry_Date': en.strftime('%Y-%m-%d'), 'Location': ln,
                                    'Status': 'Frozen' if dtype == 'Frozen' else 'Active', 'Is_Saved': 'FALSE',
                                    'Action_By': st.session_state.user_name,
                                    'Record_Status': 'In_Stock'
                                }
                                stock = pd.concat([stock, pd.DataFrame([new_r])], ignore_index=True)
                                save_data(stock, 'stock'); 
                                st.success(f"✅ รับเข้าสำเร็จ! วันผลิต: {pn.strftime('%d/%m/%Y')} | วันหมดอายุ: {en.strftime('%d/%m/%Y')}")
                                st.rerun()
                            else: st.warning("กรุณากรอกข้อมูลให้ครบถ้วน")
                with adm_t2:
                    st.info("💡 แก้ไขตารางสต็อกโดยตรง (แก้ไขเสร็จอย่าลืมกดบันทึก)")
                    ed_s_df = stock.drop(columns=['Days_Left','Total_Value','BUD_Cold','Type','merge_key'], errors='ignore').copy()
                    ed_s_df['Date_Produced'] = ed_s_df['Date_Produced'].dt.strftime('%Y-%m-%d').fillna('')
                    ed_s_df['Expiry_Date'] = ed_s_df['Expiry_Date'].dt.strftime('%Y-%m-%d').fillna('')
                    
                    ed_s = st.data_editor(ed_s_df, num_rows="dynamic", use_container_width=True)
                    if st.button("💾 บันทึกสต็อกลงระบบ"): 
                        save_data(ed_s, 'stock'); st.success("บันทึกสำเร็จ!"); st.rerun()
                with adm_t3:
                    st.info("💡 แก้ไขฐานข้อมูลรายการยาหลัก (ราคายา, อายุการใช้งาน)")
                    ed_d = st.data_editor(drugs, num_rows="dynamic", use_container_width=True)
                    if st.button("💾 บันทึกฐานข้อมูลยา"): 
                        save_data(ed_d, 'drugs'); st.success("อัปเดตข้อมูลยาสำเร็จ!"); st.rerun()
            else:
                st.warning("⛔ ขออภัยค่ะ เฉพาะสิทธิ์ผู้ดูแลระบบ (Admin) เท่านั้นที่เข้าใช้งานส่วนนี้ได้")