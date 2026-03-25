import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, timedelta
import os
import gspread
from google.oauth2.service_account import Credentials

# --- 1. SETUP & THEME ---
st.set_page_config(
    page_title="Smart Extemp Inventory - Sri Sangwan Sukhothai Hospital", 
    layout="wide", 
    page_icon="🏥"
)

# 🎨 CSS: ตกแต่ง UI และแก้ปัญหาหัวตาราง
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Prompt:wght@300;400;500;700&display=swap');
    p, div, input, button, select, h1, h2, h3, h4, h5, h6, table, th, td, label {
        font-family: 'Prompt', sans-serif;
    }
    .stDataTable th [data-testid="stTableColumnHeaderContent"] { padding-right: 25px !important; }
    [data-testid="stSidebar"] { background-color: #F2FBF2 !important; }
    h1 { color: #2E8B57 !important; font-weight: 700 !important; font-size: 32px !important; }
    .stButton>button { 
        background-color: #77DD77; color: white; border-radius: 10px; border: none; 
        font-size: 18px !important; font-weight: bold !important; 
    }
    .alert-box { padding: 12px; border-radius: 8px; margin-bottom: 8px; border-left: 6px solid; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. CONNECT TO GOOGLE SHEETS ---
SHEET_ID = "1_fd62tPsJRUONdRYlQ9hX9SOb-hPs7RCoxseK2onzYI" 
scopes = ["https://www.googleapis.com/auth/spreadsheets"]

try:
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
    _, c2, _ = st.columns([1, 2, 1])
    with c2:
        st.markdown("<h2 style='text-align:center;'>🏥 เข้าสู่ระบบ</h2>", unsafe_allow_html=True)
        user = st.text_input("Username")
        pwd = st.text_input("Password", type="password")
        if st.button("เข้าสู่ระบบ", use_container_width=True):
            if pwd == "1234":
                st.session_state.logged_in = True; st.session_state.role = user; st.rerun()
            else: st.error("รหัสผ่านไม่ถูกต้อง")
else:
    drugs, stock, locs, config = load_data()
    today = datetime.now()
    
    if not stock.empty:
        stock['Expiry_Date'] = pd.to_datetime(stock['Expiry_Date'], errors='coerce')
        stock['Date_Produced'] = pd.to_datetime(stock['Date_Produced'], errors='coerce') 
        stock['Days_Left'] = (stock['Expiry_Date'] - pd.Timestamp(today.date())).dt.days
        stock['Qty'] = pd.to_numeric(stock['Qty'], errors='coerce').fillna(0)
        
        if not drugs.empty:
            stock = stock.drop(columns=['Unit_Cost', 'Type', 'BUD_Thawed'], errors='ignore')
            stock = stock.merge(drugs[['Drug_Name', 'Unit_Cost', 'Type', 'BUD_Thawed']], on='Drug_Name', how='left')
            stock['Unit_Cost'] = pd.to_numeric(stock['Unit_Cost'], errors='coerce').fillna(0)
            stock['Total_Value'] = stock['Qty'] * stock['Unit_Cost']

    # Header
    st.markdown("<h1>Smart Extemp Inventory</h1>", unsafe_allow_html=True)

    with st.sidebar:
        st.success(f"👤 {st.session_state.role.upper()}")
        if st.button("🚪 ออกจากระบบ"): st.session_state.logged_in = False; st.rerun()
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
            c_chart = alt.Chart(stock_sum).mark_bar().encode(
                x=alt.X('Drug_Name:N', title='รายการยา', sort='-y'),
                y=alt.Y('Qty:Q', title='จำนวน'),
                color='Location:N'
            ).properties(height=300)
            st.altair_chart(c_chart, use_container_width=True)
            
            with st.expander("📋 รายละเอียดสต็อกยาเรียงตามวันหมดอายุ", expanded=True):
                detail_df = active_stock[['Drug_Name', 'Batch_ID', 'Qty', 'Location', 'Expiry_Date', 'Days_Left']].copy()
                detail_df['Expiry_Date'] = detail_df['Expiry_Date'].apply(safe_fmt)
                st.dataframe(detail_df.sort_values('Days_Left'), use_container_width=True, hide_index=True)

        st.divider()
        st.markdown("### ⚠️ แจ้งเตือนไฟจราจร")
        alerts = filtered[(filtered['Days_Left'] <= 7) & (filtered['Location'] != 'Disposal')].sort_values('Days_Left')
        for _, r in alerts.iterrows():
            c = "#FFCDD2" if r['Days_Left'] <= 3 else "#FFF9C4"
            hint = " <span style='color:#D32F2F;'>(ลืมกดละลายยา?)</span>" if r['Days_Left'] < 0 and r['Status'] == 'Frozen' else ""
            st.markdown(f"<div class='alert-box' style='background-color:{c};'><b>{r['Drug_Name']}</b> ({r['Batch_ID']}) - {r['Days_Left']} วัน 📍 {r['Location']}{hint}</div>", unsafe_allow_html=True)

        st.divider()
        c_th, c_di, c_wa = st.columns(3)
        
        # --- 1. ปรับปรุงหมวดละลายยา ---
        with c_th:
            st.markdown("#### ❄️ ละลายยา (Frozen)")
            if 'Type' in filtered.columns:
                f_items = filtered[(filtered['Type'] == 'Frozen') & (filtered['Status'] == 'Frozen')]
                
                # ระบบเตือนเฉพาะตัวที่ใกล้หมดอายุ (<= 3 วัน) หรือ ลืมกด (< 0)
                f_alerts = f_items[f_items['Days_Left'] <= 3].sort_values('Days_Left')
                if not f_alerts.empty:
                    for _, r in f_alerts.iterrows():
                        if r['Days_Left'] < 0:
                            st.markdown(f"<div style='color:#D32F2F; font-size:14px; font-weight:bold;'>❌ เลยกำหนด: {r['Drug_Name']} (ลืมกดละลาย?)</div>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"<div style='color:#F57C00; font-size:14px; font-weight:bold;'>⚠️ เหลือ {r['Days_Left']} วัน: {r['Drug_Name']}</div>", unsafe_allow_html=True)
                
                # เปลี่ยนจากปุ่มรวดเดียว เป็น Dropdown ให้เลือก
                if not f_items.empty:
                    thaw_sel = st.selectbox("เลือกยาที่ต้องการละลาย:", f_items.apply(lambda x: f"{x['Drug_Name']} (Batch: {x['Batch_ID']})", axis=1), index=None, key="thaw_sel")
                    if thaw_sel:
                        t_bid = thaw_sel.split("Batch: ")[1].split(")")[0]
                        if st.button("💧 ยืนยันละลายยา", type="primary", use_container_width=True):
                            t_row = stock[stock['Batch_ID']==t_bid].iloc[0]
                            bud = int(t_row['BUD_Thawed']) if str(t_row['BUD_Thawed']).isdigit() else 0
                            # เปลี่ยน Status และตั้งวันหมดอายุใหม่นับจาก "วันนี้"
                            stock.loc[stock['Batch_ID']==t_bid, ['Status', 'Expiry_Date']] = ['Thawed', today + timedelta(days=bud)]
                            save_data(stock, 'stock'); st.success("ละลายยาสำเร็จ!"); st.rerun()
                else: st.info("ไม่มียาแช่แข็งในระบบ")
            else: st.info("ไม่มียาแช่แข็งในระบบ")

        with c_di:
            st.markdown("#### ✂️ ตัดจ่ายยาปกติ")
            d_l = st.selectbox("จากห้อง:", active_locs, index=None, placeholder="-- เลือกห้อง --", key="d_l")
            if d_l:
                d_items = stock[stock['Location'] == d_l]
                if not d_items.empty:
                    d_sel = st.selectbox("เลือกยา:", d_items.apply(lambda x: f"{x['Drug_Name']} (Batch: {x['Batch_ID']}) [เหลือ {int(x['Qty'])}]", axis=1), index=None)
                    if d_sel:
                        bid = d_sel.split("Batch: ")[1].split(")")[0]
                        max_q = int(stock.loc[stock['Batch_ID']==bid, 'Qty'].values[0])
                        q_cut = st.number_input("จำนวนจ่าย:", 1, max_q, max_q)
                        if st.button("✅ ยืนยันจ่าย"):
                            if max_q - q_cut <= 0: stock = stock[stock['Batch_ID']!=bid]
                            else: stock.loc[stock['Batch_ID']==bid, 'Qty'] = max_q - q_cut
                            save_data(stock, 'stock'); st.success("สำเร็จ!"); st.rerun()
                else: st.warning("ไม่มีรายการยา")

        with c_wa:
            st.markdown("#### 🗑️ ตัดยาทิ้ง/หมดอายุ")
            w_l = st.selectbox("ทิ้งจาก:", active_locs, index=None, placeholder="-- เลือกห้อง --", key="w_l")
            if w_l:
                w_items = stock[stock['Location'] == w_l]
                if not w_items.empty:
                    w_sel = st.selectbox("เลือกยาที่ทิ้ง:", w_items.apply(lambda x: f"{x['Drug_Name']} (Batch: {x['Batch_ID']}) [เหลือ {int(x['Qty'])}]", axis=1), index=None)
                    if w_sel:
                        wbid = w_sel.split("Batch: ")[1].split(")")[0]
                        wmax = int(stock.loc[stock['Batch_ID']==wbid, 'Qty'].values[0])
                        q_w = st.number_input("จำนวนทิ้ง:", 1, wmax, wmax)
                        if st.button("🗑️ ยืนยันการทิ้ง", type="primary"):
                            if wmax - q_w <= 0: stock.loc[stock['Batch_ID']==wbid, 'Location'] = 'Disposal'
                            else:
                                stock.loc[stock['Batch_ID']==wbid, 'Qty'] = wmax - q_w
                                new_w = stock[stock['Batch_ID']==wbid].iloc[0].copy()
                                new_w['Qty'] = q_w; new_w['Location'] = 'Disposal'
                                stock = pd.concat([stock, pd.DataFrame([new_w])], ignore_index=True)
                            save_data(stock, 'stock'); st.error("บันทึกการทิ้งสำเร็จ"); st.rerun()
                            
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
