import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, timedelta
import os
import gspread
from google.oauth2.service_account import Credentials
import re

# --- 1. SETUP & THEME ---
st.set_page_config(
    page_title="Smart Extemp Inventory - Pharmacy Srisangworn Sukhothai Hospital", 
    layout="wide", 
    page_icon="SSW_Logo.jpg" # 🌟 แสดงโลโก้ที่ Tab ของ Web Browser
)

# 🎨 CSS: ตกแต่ง UI ให้เป็นโทนพาสเทล
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Prompt:wght@300;400;500;700&display=swap');
    p, div, input, button, select, h1, h2, h3, h4, h5, h6, table, th, td, label {
        font-family: 'Prompt', sans-serif;
    }
    .stDataTable th [data-testid="stTableColumnHeaderContent"] { padding-right: 25px !important; }
    [data-testid="stSidebar"] { background-color: #F2FBF2 !important; }
    h1 { color: #2E8B57 !important; font-weight: 700 !important; font-size: 32px !important; margin-bottom: 0px !important; padding-bottom: 0px !important; line-height: 1.2;}
    h3.sub-header { color: #666666 !important; font-weight: 500 !important; font-size: 20px !important; margin-top: 5px !important; padding-top: 0px !important;}
    .stButton>button { 
        background-color: #77DD77; color: white; border-radius: 10px; border: none; 
        font-size: 18px !important; font-weight: bold !important; 
    }
    .alert-box { padding: 12px; border-radius: 8px; margin-bottom: 8px; border-left: 6px solid; }
    
    /* เปลี่ยนสีกล่องหน่วยงาน (Multiselect tags) ให้เป็นสีพาสเทลเขียว */
    span[data-baseweb="tag"] {
        background-color: #A8E6CF !important;
        color: #1E5631 !important;
    }
    /* จัดกึ่งกลางโลโก้ในหน้า Login */
    .login-logo { display: flex; justify-content: center; margin-bottom: 15px; }
    </style>
    """, unsafe_allow_html=True)

import json # เพิ่ม import json ไว้ส่วนบนสุดด้วยนะคะ

# --- 2. CONNECT TO GOOGLE SHEETS ---
SHEET_ID = "1_fd62tPsJRUONdRYlQ9hX9SOb-hPs7RCoxseK2onzYI" 
scopes = ["https://www.googleapis.com/auth/spreadsheets"]

try:
    # ระบบจะเช็คว่ามีรหัสลับบน Cloud ไหม ถ้าไม่มีจะดึงจากไฟล์ key.json ในคอมแทน
    if "google_credentials" in st.secrets:
        creds_dict = json.loads(st.secrets["google_credentials"])
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
            
            df = pd.DataFrame(values[1:], columns=values[0])
            df.columns = df.columns.astype(str).str.strip()
            return df
        except Exception as e: 
            return pd.DataFrame() 
    return get_sheet_df("Drugs"), get_sheet_df("Stock"), get_sheet_df("Locations"), get_sheet_df("Users")

def save_data(df, file_name):
    if df is None or df.empty or len(df.columns) == 0:
        st.error("⚠️ ตรวจพบตารางข้อมูลว่างเปล่า ระบบระงับการบันทึกเพื่อป้องกันข้อมูลสูญหาย")
        return

    file_key = file_name.replace('.csv', '').upper()
    tab_name = 'Stock' if 'STOCK' in file_key else ('Drugs' if 'DRUG' in file_key else 'Locations')
    
    df_clean = df.copy()
    if tab_name == 'Stock':
        cols_to_drop = ['Days_Left', 'Total_Value', 'Unit_Cost', 'Type', 'BUD_Cold', 'merge_key']
        df_clean = df_clean.drop(columns=[c for c in cols_to_drop if c in df_clean.columns], errors='ignore')
    
    try:
        df_safe = df_clean.astype(str).replace(['nan', 'NaT', 'None'], '')
        data_to_upload = [df_safe.columns.tolist()] + df_safe.values.tolist()
        worksheet = gsheet.worksheet(tab_name)
        worksheet.clear()
        worksheet.update(data_to_upload)
    except Exception as e:
        st.error(f"❌ บันทึกไม่สำเร็จ: {e}")

# --- 4. MAIN APPLICATION ---
drugs, stock, locs, users_df = load_data()

if 'logged_in' not in st.session_state: 
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    _, c2, _ = st.columns([1, 2, 1])
    with c2:
        # 🌟 จุดที่ 1: เพิ่มโลโก้หน้า Login 🌟
        try:
            col_img1, col_img2, col_img3 = st.columns([1, 1.5, 1])
            with col_img2:
                st.image("SSW_Logo.jpg", use_container_width=True)
        except Exception:
            pass # ซ่อน Error หากหาไฟล์รูปภาพไม่พบ
            
        st.markdown("<h2 style='text-align:center;'>🏥 เข้าสู่ระบบ</h2>", unsafe_allow_html=True)
        user_input = st.text_input("Username")
        pwd_input = st.text_input("Password", type="password")
        
        if st.button("เข้าสู่ระบบ", use_container_width=True):
            if users_df.empty:
                st.error("❌ ไม่พบแท็บ 'Users' ใน Google Sheets หรือตารางยังว่างอยู่")
            else:
                users_df['Username'] = users_df['Username'].astype(str).str.strip()
                users_df['Password'] = users_df['Password'].astype(str).str.strip()
                matched_user = users_df[(users_df['Username'] == user_input.strip()) & (users_df['Password'] == str(pwd_input).strip())]
                
                if not matched_user.empty:
                    st.session_state.logged_in = True
                    st.session_state.role = str(matched_user.iloc[0].get('Role', 'staff')).lower()
                    st.session_state.user_name = str(matched_user.iloc[0].get('Name', user_input))
                    st.rerun()
                else: 
                    st.error("❌ Username หรือ Password ไม่ถูกต้อง")

else:
    today = datetime.now()
    
    if not stock.empty:
        if 'Status' not in stock.columns: stock['Status'] = 'Active'
        if 'Action_By' not in stock.columns: stock['Action_By'] = '-'

        def parse_smart_date(d):
            if pd.isna(d): return pd.NaT
            d = str(d).strip()
            if d in ['', 'None', 'NaT', 'nan', '<NA>']: return pd.NaT
            match = re.search(r'(\d{4})', d)
            if match:
                year = int(match.group(1))
                if year >= 2500: d = d.replace(str(year), str(year - 543))
            try:
                return pd.to_datetime(d, dayfirst=True)
            except:
                return pd.NaT

        stock['Expiry_Date'] = stock['Expiry_Date'].apply(parse_smart_date)
        stock['Date_Produced'] = stock['Date_Produced'].apply(parse_smart_date) 
        stock['Days_Left'] = (stock['Expiry_Date'] - pd.Timestamp(today.date())).dt.days
        stock['Qty'] = pd.to_numeric(stock['Qty'], errors='coerce').fillna(0)
        
        if not drugs.empty:
            stock['merge_key'] = stock['Drug_Name'].astype(str).str.replace(r'\s+', '', regex=True).str.lower()
            drugs['merge_key'] = drugs['Drug_Name'].astype(str).str.replace(r'\s+', '', regex=True).str.lower()
            
            unit_cost_col = next((c for c in drugs.columns if 'cost' in str(c).lower() or 'ราคา' in str(c)), None)
            type_col = next((c for c in drugs.columns if 'type' in str(c).lower() or 'ประเภท' in str(c)), None)
            bud_cold_col = next((c for c in drugs.columns if 'cold' in str(c).lower()), None)
            
            cols_to_merge = ['merge_key']
            if unit_cost_col: cols_to_merge.append(unit_cost_col)
            if type_col: cols_to_merge.append(type_col)
            if bud_cold_col: cols_to_merge.append(bud_cold_col)
            
            stock = stock.drop(columns=['Unit_Cost', 'Type', 'BUD_Cold'], errors='ignore')
            stock = stock.merge(drugs[cols_to_merge], on='merge_key', how='left')
            
            rename_dict = {}
            if unit_cost_col: rename_dict[unit_cost_col] = 'Unit_Cost'
            if type_col: rename_dict[type_col] = 'Type'
            if bud_cold_col: rename_dict[bud_cold_col] = 'BUD_Cold'
            stock = stock.rename(columns=rename_dict)
            
            if 'Unit_Cost' not in stock.columns: stock['Unit_Cost'] = 0
            if 'Type' not in stock.columns: stock['Type'] = 'Room'
            if 'BUD_Cold' not in stock.columns: stock['BUD_Cold'] = 0
            
            stock['Unit_Cost'] = stock['Unit_Cost'].astype(str).replace(r'[^\d.]', '', regex=True)
            stock['Unit_Cost'] = pd.to_numeric(stock['Unit_Cost'], errors='coerce').fillna(0)
            stock['Total_Value'] = (stock['Qty'] * stock['Unit_Cost']).astype(float)
            
            stock = stock.drop(columns=['merge_key'], errors='ignore')
            drugs = drugs.drop(columns=['merge_key'], errors='ignore')

    # Header ส่วนบนสุด
    st.markdown("""
        <div style="margin-bottom: 25px;">
            <h1>Smart Extemp Inventory</h1>
            <h3 class="sub-header">Pharmacy Srisangworn Sukhothai Hospital</h3>
        </div>
    """, unsafe_allow_html=True)

    with st.sidebar:
        # 🌟 จุดที่ 2: เพิ่มโลโก้ที่แถบเมนูด้านซ้าย 🌟
        try:
            st.image("SSW_Logo.jpg", use_container_width=True)
            st.markdown("<br>", unsafe_allow_html=True) # เว้นบรรทัดให้สวยงาม
        except Exception:
            pass
            
        st.success(f"👤 คุณ {st.session_state.user_name} \n\n🔑 สิทธิ์: {st.session_state.role.upper()}")
        if st.button("🚪 ออกจากระบบ"): 
            st.session_state.logged_in = False
            st.rerun()
        
        active_locs = locs['Location'].unique().tolist() if not locs.empty else []
        loc_filter = st.multiselect("เลือกดูหน่วยงาน:", active_locs, default=active_locs)

    filtered = stock[stock['Location'].isin(loc_filter)].copy()
    tab1, tab2, tab3 = st.tabs(["🚨 บริการ (Service)", "📊 ผู้บริหาร (Executive)", "⚙️ หลังบ้าน (Admin)"])

    # === TAB 1: SERVICE ===
    with tab1:
        st.markdown("### 📦 ภาพรวมสต็อกยา")
        active_stock = stock[stock['Location'] != 'Disposal']
        if not active_stock.empty:
            stock_sum = active_stock.groupby(['Drug_Name', 'Location'])['Qty'].sum().reset_index()
            
            # สีกราฟเป็นโทนพาสเทลฟ้า/น้ำเงิน
            pastel_blues = ['#AEC6CF', '#89CFF0', '#B4CFEC', '#C6DEFF', '#ADD8E6', '#B0E0E6', '#9ACEEB']
            
            c_chart = alt.Chart(stock_sum).mark_bar().encode(
                x=alt.X('Drug_Name:N', title='รายการยา', sort='-y'),
                y=alt.Y('Qty:Q', title='จำนวน'),
                color=alt.Color('Location:N', scale=alt.Scale(range=pastel_blues)),
                tooltip=['Drug_Name', 'Location', 'Qty']
            ).properties(height=300)
            st.altair_chart(c_chart, use_container_width=True)
            
            with st.expander("📋 รายละเอียดสต็อกยาเรียงตามวันหมดอายุ", expanded=True):
                detail_df = active_stock[['Drug_Name', 'Batch_ID', 'Qty', 'Location', 'Status', 'Expiry_Date', 'Days_Left', 'Action_By']].copy()
                detail_df['Expiry_Date'] = detail_df['Expiry_Date'].apply(safe_fmt)
                st.dataframe(detail_df.sort_values('Days_Left'), use_container_width=True, hide_index=True)

        st.divider()
        st.markdown("### ⚠️ แจ้งเตือนยาใกล้หมดอายุ")
        
        alerts = filtered[(filtered['Days_Left'] <= 7) & (filtered['Location'] != 'Disposal')].sort_values('Days_Left')
        if alerts.empty: 
            st.success("✅ ไม่มียาใกล้หมดอายุใน 7 วันนี้")
        for _, r in alerts.iterrows():
            c = "#FFCDD2" if r['Days_Left'] <= 3 else "#FFF9C4"
            st.markdown(f"<div class='alert-box' style='background-color:{c};'><b>{r['Drug_Name']}</b> ({r['Batch_ID']}) - เหลือเวลา {r['Days_Left']} วัน 📍 {r['Location']}</div>", unsafe_allow_html=True)

        st.divider()
        
        c_th, c_di, c_tr, c_wa = st.columns(4)
        
        with c_th:
            st.markdown("#### ❄️ เตือนละลายยา")
            if 'Type' in filtered.columns:
                f_items = filtered[(filtered['Type'] == 'Frozen') & (filtered['Status'] == 'Frozen')]
                if not f_items.empty:
                    for _, r in f_items.iterrows():
                        if st.button(f"💧 นำออกตู้แช่: {r['Drug_Name']} ({r['Batch_ID']})"):
                            match = re.search(r'\d+', str(r.get('BUD_Cold', 0)))
                            bud = int(match.group()) if match else 0
                            new_exp = today + timedelta(days=bud)
                            
                            stock.loc[stock['Batch_ID']==r['Batch_ID'], ['Status', 'Expiry_Date', 'Action_By']] = ['Thawed', new_exp, st.session_state.user_name]
                            save_data(stock, 'stock')
                            st.success(f"คำนวณวันหมดอายุใหม่สำเร็จ: {new_exp.strftime('%d/%m/%Y')}")
                            st.rerun()
                else: st.info("ไม่มียาแช่แข็งในสต็อกตอนนี้")

        with c_di:
            st.markdown("#### ✂️ ตัดจ่ายปกติ")
            d_l = st.selectbox("จากห้อง:", active_locs, index=None, placeholder="-- เลือกห้อง --", key="d_l")
            if d_l:
                d_items = stock[stock['Location'] == d_l]
                if not d_items.empty:
                    d_sel = st.selectbox("เลือกยา:", d_items.apply(lambda x: f"{x['Drug_Name']} ({x['Batch_ID']}) [เหลือ {int(x['Qty'])}]", axis=1), index=None)
                    if d_sel:
                        bid = d_sel.split("(")[1].split(")")[0]
                        max_q = int(stock.loc[stock['Batch_ID']==bid, 'Qty'].values[0])
                        q_cut = st.number_input("จำนวนจ่าย:", 1, max_q, max_q)
                        if st.button("✅ ยืนยันจ่าย"):
                            if max_q - q_cut <= 0: 
                                stock = stock[stock['Batch_ID']!=bid]
                            else: 
                                stock.loc[stock['Batch_ID']==bid, 'Qty'] = max_q - q_cut
                                stock.loc[stock['Batch_ID']==bid, 'Action_By'] = f"เบิกจ่ายโดย {st.session_state.user_name}"
                            save_data(stock, 'stock'); st.success("สำเร็จ!"); st.rerun()
                else: st.warning("ไม่มีรายการยา")

        with c_tr:
            st.markdown("#### 🔄 ช่วยกันใช้")
            t_from = st.selectbox("จากห้อง:", active_locs, index=None, placeholder="-- ต้นทาง --", key="t_from")
            t_to = st.selectbox("ไปห้อง:", active_locs, index=None, placeholder="-- ปลายทาง --", key="t_to")
            if t_from and t_to and t_from != t_to:
                t_items = stock[stock['Location'] == t_from].sort_values('Drug_Name')
                if not t_items.empty:
                    t_sel = st.selectbox("เลือกยาโอน:", t_items.apply(lambda x: f"{x['Drug_Name']} ({x['Batch_ID']}) [มี {int(x['Qty'])}]", axis=1), index=None)
                    if t_sel:
                        tbid = t_sel.split("(")[1].split(")")[0]
                        tmax = int(stock.loc[stock['Batch_ID']==tbid, 'Qty'].values[0])
                        q_t = st.number_input("จำนวนโอน:", 1, tmax, tmax, key="q_t")
                        if st.button("🔄 ยืนยันโอนยา", type="secondary"):
                            if tmax - q_t <= 0: 
                                stock.loc[stock['Batch_ID']==tbid, ['Location', 'Status', 'Action_By']] = [t_to, 'Transferred', st.session_state.user_name]
                            else:
                                stock.loc[stock['Batch_ID']==tbid, 'Qty'] = tmax - q_t
                                new_t = stock[stock['Batch_ID']==tbid].iloc[0].copy()
                                new_t['Qty'] = q_t
                                new_t['Location'] = t_to
                                new_t['Status'] = 'Transferred' 
                                new_t['Action_By'] = st.session_state.user_name
                                stock = pd.concat([stock, pd.DataFrame([new_t])], ignore_index=True)
                            save_data(stock, 'stock')
                            st.success(f"โอนไปยัง {t_to} สำเร็จ!")
                            st.rerun()
                else: st.warning("ไม่มียาในห้องนี้")

        with c_wa:
            st.markdown("#### 🗑️ ตัดยาหมดอายุ")
            w_l = st.selectbox("ทิ้งจาก:", active_locs, index=None, placeholder="-- เลือกห้อง --", key="w_l")
            if w_l:
                w_items = stock[stock['Location'] == w_l]
                if not w_items.empty:
                    w_sel = st.selectbox("เลือกยาที่ทิ้ง:", w_items.apply(lambda x: f"{x['Drug_Name']} ({x['Batch_ID']}) [เหลือ {int(x['Qty'])}]", axis=1), index=None)
                    if w_sel:
                        wbid = w_sel.split("(")[1].split(")")[0]
                        wmax = int(stock.loc[stock['Batch_ID']==wbid, 'Qty'].values[0])
                        q_w = st.number_input("จำนวนทิ้ง:", 1, wmax, wmax)
                        if st.button("🗑️ ยืนยันการทิ้ง", type="primary"):
                            if wmax - q_w <= 0: 
                                stock.loc[stock['Batch_ID']==wbid, ['Location', 'Action_By']] = ['Disposal', st.session_state.user_name]
                            else:
                                stock.loc[stock['Batch_ID']==wbid, 'Qty'] = wmax - q_w
                                new_w = stock[stock['Batch_ID']==wbid].iloc[0].copy()
                                new_w['Qty'] = q_w
                                new_w['Location'] = 'Disposal'
                                new_w['Action_By'] = st.session_state.user_name
                                stock = pd.concat([stock, pd.DataFrame([new_w])], ignore_index=True)
                            save_data(stock, 'stock'); st.error("บันทึกการทิ้งสำเร็จ"); st.rerun()

    # === TAB 2: EXECUTIVE ===
    with tab2:
        st.markdown("### 📊 สรุปรายงานมูลค่าและการบริหารจัดการ")
        
        c_date1, c_date2 = st.columns(2)
        sd = c_date1.date_input("รอบบิล เริ่มต้น:", today.date() - timedelta(days=90))
        ed = c_date2.date_input("รอบบิล สิ้นสุด:", today.date())
        
        st_date = pd.to_datetime(stock['Date_Produced'], errors='coerce')
        mask = (st_date.dt.date >= sd) & (st_date.dt.date <= ed)
        t2_stock = stock[mask].copy()
        
        if not t2_stock.empty:
            v_total = t2_stock[t2_stock['Location'] != 'Disposal']['Total_Value'].sum()
            v_waste = t2_stock[t2_stock['Location'] == 'Disposal']['Total_Value'].sum()
            v_saved = t2_stock[(t2_stock['Status'] == 'Transferred') & (t2_stock['Location'] != 'Disposal')]['Total_Value'].sum()

            m1, m2, m3 = st.columns(3)
            m1.metric("📦 มูลค่ายาคงคลัง", f"฿ {v_total:,.2f}", "ยอดรวมในระบบ")
            m2.metric("♻️ มูลค่าประหยัดได้ (ช่วยกันใช้)", f"฿ {v_saved:,.2f}", "ลดการหมดอายุ")
            m3.metric("🗑️ มูลค่าสูญเสีย (ทิ้ง/หมดอายุ)", f"฿ {v_waste:,.2f}", "- ต้นทุนที่เสียไป", delta_color="inverse")

            st.divider()
            
            st.markdown("#### 🔍 รายละเอียดข้อมูลยา (Drill-down)")
            view_type = st.radio("เลือกดูข้อมูล:", ["ดูรายการยาคงคลังทั้งหมด", "ดูรายการยาที่โอนช่วยกันใช้", "ดูรายการยาที่สูญเสีย (ทิ้ง)"], horizontal=True)
            
            if view_type == "ดูรายการยาที่สูญเสีย (ทิ้ง)":
                df_show = t2_stock[t2_stock['Location'] == 'Disposal']
            elif view_type == "ดูรายการยาที่โอนช่วยกันใช้":
                df_show = t2_stock[t2_stock['Status'] == 'Transferred']
            else:
                df_show = t2_stock[t2_stock['Location'] != 'Disposal']
                
            if not df_show.empty:
                st.dataframe(
                    df_show[['Drug_Name', 'Batch_ID', 'Qty', 'Location', 'Total_Value', 'Action_By']].style.format({'Total_Value': '{:,.2f}'}), 
                    use_container_width=True, hide_index=True
                )
            else:
                st.info("ไม่มีข้อมูลในหมวดหมู่นี้สำหรับช่วงเวลาที่เลือก")

    # === TAB 3: ADMIN ===
    with tab3:
        if st.session_state.role == 'admin':
            adm_t1, adm_t2, adm_t3 = st.tabs(["📥 รับยาเข้า", "🛠️ แก้ไขสต็อก", "💊 จัดการฐานข้อมูลยา (Master Data)"])
            
            with adm_t1:
                with st.form("in_form", clear_on_submit=True):
                    c1, c2 = st.columns(2)
                    dn = c1.selectbox("ชื่อยา:", drugs['Drug_Name'].unique(), index=None)
                    bn = c1.text_input("Batch ID:")
                    qn = c2.number_input("จำนวน:", min_value=1)
                    pn = c2.date_input("วันผลิต:", today)
                    ln = c2.selectbox("ห้องเก็บ:", active_locs, index=None)
                    
                    if st.form_submit_button("บันทึกรับเข้า"):
                        if dn and bn and ln:
                            try:
                                dinfo = drugs[drugs['Drug_Name']==dn].iloc[0]
                                dtype = str(dinfo.get('Type', 'Room')).strip()
                                
                                bud_val = 0
                                if dtype == 'Frozen': bud_val = dinfo.get('BUD_Frozen', 0)
                                elif dtype == 'Cold': bud_val = dinfo.get('BUD_Cold', 0)
                                else: bud_val = dinfo.get('BUD_Room', 0)
                                
                                match = re.search(r'\d+', str(bud_val))
                                days = int(match.group()) if match else 0
                                
                                en = pn + timedelta(days=days)
                                
                                new_r = {
                                    'Date_Produced': pn.strftime('%Y-%m-%d'), 
                                    'Drug_Name': dn, 
                                    'Batch_ID': bn,
                                    'Qty': qn, 
                                    'Expiry_Date': en.strftime('%Y-%m-%d'), 
                                    'Location': ln,
                                    'Status': 'Frozen' if dtype == 'Frozen' else 'Active', 
                                    'Is_Saved': 'FALSE',
                                    'Action_By': st.session_state.user_name
                                }
                                
                                stock = pd.concat([stock, pd.DataFrame([new_r])], ignore_index=True)
                                save_data(stock, 'stock')
                                st.success(f"✅ รับเข้า {dn} สำเร็จ! (วันหมดอายุ: {en.strftime('%d/%m/%Y')})")
                                st.rerun()
                                
                            except Exception as e:
                                st.error(f"❌ ระบบขัดข้องระหว่างคำนวณวันหมดอายุ: {e}")
                        else:
                            st.warning("⚠️ กรุณากรอกข้อมูลให้ครบถ้วน")

            with adm_t2:
                st.info("💡 หากแก้ไขตารางสต็อกโดยตรง ระบบจะยึดตามข้อมูลในตารางนี้เป็นหลัก")
                ed_s = st.data_editor(stock.drop(columns=['Days_Left','Total_Value','BUD_Cold','Type'], errors='ignore'), num_rows="dynamic")
                if st.button("💾 บันทึกสต็อกลง Cloud"): 
                    save_data(ed_s, 'stock')
                    st.success("บันทึกการแก้ไขสต็อกสำเร็จ!")
                    st.rerun()
                    
            with adm_t3:
                st.markdown("#### 📝 แก้ไขฐานข้อมูลรายการยาหลัก (Drug Master Data)")
                edited_drugs = st.data_editor(drugs, num_rows="dynamic", use_container_width=True)
                if st.button("💾 บันทึกฐานข้อมูลยาลง Cloud", type="primary"): 
                    save_data(edited_drugs, 'drugs')
                    st.success("✅ อัปเดตฐานข้อมูลยาเรียบร้อยแล้ว!")
                    st.rerun()
        else:
            st.warning("⛔ คุณไม่มีสิทธิ์เข้าถึงส่วนผู้ดูแลระบบ (Admin)")