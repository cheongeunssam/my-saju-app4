import streamlit as st
import ephem
import datetime
import math
from korean_lunar_calendar import KoreanLunarCalendar

# ==========================================
# 0. 캐싱 및 엔진 설정 (결과 고정)
# ==========================================
# 이 데코레이터를 쓰면, 입력값(생년월일시)이 같을 때 
# 다시 계산하지 않고 저장된 결과를 그대로 보여줍니다. (속도 UP, 일관성 UP)
@st.cache_data
def calculate_saju_cached(year, month, day, hour, minute, gender, name):
    engine = SajuEngine()
    return engine.calculate(year, month, day, hour, minute, gender, name)

# ==========================================
# 1. 청은(靑隱) 통합 엔진 (V40)
# ==========================================
class SajuEngine:
    def __init__(self):
        self.cheon = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸']
        self.ji = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥']
        self.sibsin_names = ['비견', '겁재', '식신', '상관', '편재', '정재', '편관', '정관', '편인', '정인']
        self.unseong_names = ['장생', '목욕', '관대', '건록', '제왕', '쇠', '병', '사', '묘', '절', '태', '양']
        self.c_data = [(0,0), (0,1), (1,0), (1,1), (2,0), (2,1), (3,0), (3,1), (4,0), (4,1)]
        self.j_data = [(4,1), (2,1), (0,0), (0,1), (2,0), (1,0), (1,1), (2,1), (3,0), (3,1), (2,0), (4,0)]
        self.unseong_start = [11, 6, 2, 9, 2, 9, 5, 0, 8, 3]

    def _get_ganji(self, gan_idx, ji_idx):
        return f"{self.cheon[gan_idx % 10]}{self.ji[ji_idx % 12]}"

    def _get_sibsin(self, me_idx, target_idx, is_target_cheon=True):
        me_elem, me_pol = self.c_data[me_idx]
        if is_target_cheon: tgt_elem, tgt_pol = self.c_data[target_idx]
        else: tgt_elem, tgt_pol = self.j_data[target_idx]
        rel = (tgt_elem - me_elem + 5) % 5
        is_diff = 0 if me_pol == tgt_pol else 1
        return self.sibsin_names[rel * 2 + is_diff]

    def _get_12unseong(self, day_gan_idx, ji_idx):
        start_ji = self.unseong_start[day_gan_idx]
        is_yang = (day_gan_idx % 2 == 0)
        if is_yang: offset = (ji_idx - start_ji + 12) % 12
        else: offset = (start_ji - ji_idx + 12) % 12
        return self.unseong_names[offset]

    def get_gongmang(self, day_gan, day_ji):
        start_idx = (day_ji - day_gan + 12) % 12
        gm1 = self.ji[(start_idx + 10) % 12]
        gm2 = self.ji[(start_idx + 11) % 12]
        return f"{gm1}{gm2}"

    def get_shinsal(self, day_gan, day_ji, target_ji):
        shinsal_list = []
        groups = {0: 2, 4: 2, 8: 2, 2: 1, 6: 1, 10: 1, 3: 0, 7: 0, 11: 0, 5: 3, 9: 3, 1: 3}
        dohwa_map = {2: 9, 1: 3, 0: 0, 3: 6}
        yeokma_map = {2: 2, 1: 8, 0: 5, 3: 11}
        hwagae_map = {2: 4, 1: 10, 0: 7, 3: 1}
        if target_ji == dohwa_map[groups[day_ji]]: shinsal_list.append("도화")
        if target_ji == yeokma_map[groups[day_ji]]: shinsal_list.append("역마")
        if target_ji == hwagae_map[groups[day_ji]]: shinsal_list.append("화개")
        gwin_map = {0: [1, 7], 4: [1, 7], 6: [1, 7], 1: [0, 8], 5: [0, 8], 2: [11, 9], 3: [11, 9], 7: [2, 6], 8: [5, 3], 9: [5, 3]}
        if target_ji in gwin_map[day_gan]: shinsal_list.append("천을귀인")
        return ",".join(shinsal_list) if shinsal_list else "-"

    def check_baekho(self, gan, ji):
        baekho = [(0,4), (1,7), (2,10), (3,1), (4,4), (8,10), (9,1)]
        return "백호" if (gan, ji) in baekho else ""
    
    def check_goemigwan(self, gan, ji):
        goe = [(4,10), (6,4), (6,10), (8,4), (8,10), (4,4)]
        return "괴강" if (gan, ji) in goe else ""

    def get_daewoon_data(self, kst_date, direction):
        utc_date = kst_date - datetime.timedelta(hours=9)
        sun = ephem.Sun()
        sun.compute(utc_date)
        start_lon = math.degrees(ephem.Ecliptic(sun).lon)
        start_term_idx = int(start_lon / 15)
        
        check_date = utc_date
        found_date = None
        
        for i in range(1, 1080): 
            check_date += datetime.timedelta(hours=1 * direction)
            sun.compute(check_date)
            curr_lon = math.degrees(ephem.Ecliptic(sun).lon)
            if curr_lon < 0: curr_lon += 360
            curr_term_idx = int(curr_lon / 15)
            if curr_term_idx != start_term_idx:
                found_date = check_date
                break
        
        if not found_date: return 1, "절기 탐색 실패"

        diff_seconds = abs((found_date - utc_date).total_seconds())
        diff_days = diff_seconds / 86400.0
        
        raw_num = diff_days / 3.0
        daewoon_num = int(raw_num)
        remainder = diff_days % 3
        if remainder > 2: daewoon_num += 1
        if daewoon_num < 1: daewoon_num = 1
        return daewoon_num, ""

    def generate_detailed_report(self, day_gan_idx, name):
        my_char = self.cheon[day_gan_idx]
        report = {}
        report['header'] = f"{name}님의 2026 병오년 전략 리포트"
        
        # 10천간 전략 (결과 고정)
        if my_char == '甲': 
            report['summary'] = {"keywords": ["급성장", "에너지방출", "체력관리"], "score": 88, "desc": "거대한 나무가 태양을 만나 꽃을 피우는 형국입니다."}
            report['wealth'] = "활동한 만큼 정직하게 수익이 발생합니다. 불로소득보다는 본업에서의 인센티브가 큽니다."
            report['career'] = "승진운과 이직운이 동시에 들어옵니다. 내 목소리가 커지고 리더십을 발휘하게 됩니다."
            report['timing'] = "2월, 5월 (행운) / 8월 (주의)"
            report['qimen'] = {"dir": "남쪽 (離宮)", "action": "경문(景門)이 열렸으니 화려하게 치장하고 드러내십시오.", "color": "Red & Purple"}
        elif my_char == '乙': 
            report['summary'] = {"keywords": ["인기상승", "화려함", "표현력"], "score": 92, "desc": "아름다운 화초가 햇살을 받아 만발합니다. 주목받고 인기가 치솟는 운입니다."}
            report['wealth'] = "사람을 통해 돈이 들어옵니다. 영업, 서비스, 교육 분야라면 매출이 급증합니다."
            report['career'] = "프레젠테이션이나 발표에서 대박이 납니다. 당신의 말 한마디가 천냥 빚을 갚습니다."
            report['timing'] = "3월, 6월 (행운) / 9월 (주의)"
            report['qimen'] = {"dir": "동남쪽 (巽宮)", "action": "바람을 타고 멀리 퍼져나가십시오. 소식이 닿는 곳이 길합니다.", "color": "Green & Pink"}
        elif my_char == '丙': 
            report['summary'] = {"keywords": ["치열한경쟁", "독보적존재", "자존심"], "score": 78, "desc": "하늘에 태양이 두 개 뜬 형국입니다. 경쟁자가 나타나지만 결국 당신이 더 빛날 것입니다."}
            report['wealth'] = "돈이 들어오자마자 나갈 곳이 생깁니다. 형제나 친구로 인한 지출을 경계하십시오."
            report['career'] = "경쟁 PT나 입찰에서 승리할 운입니다. 다만 독단적인 결정은 팀 내 불화를 만듭니다."
            report['timing'] = "2월, 5월 (행운) / 11월 (주의)"
            report['qimen'] = {"dir": "서쪽 (兌宮)", "action": "경문(驚門)을 조심하고 실리를 챙기세요.", "color": "White & Gold"}
        elif my_char == '丁': 
            report['summary'] = {"keywords": ["등라계갑", "귀인협력", "실속"], "score": 85, "desc": "촛불이 용광로를 만난 격입니다. 혼자서는 힘든 일을 파트너의 도움으로 해결합니다."}
            report['wealth'] = "작지만 알찬 수익이 지속됩니다. 큰 한 방보다는 파이프라인 확장에 주력하세요."
            report['career'] = "윗사람보다는 동료나 거래처의 도움이 큽니다. 겸손하게 도움을 요청하면 해결됩니다."
            report['timing'] = "5월, 6월 (행운) / 10월 (주의)"
            report['qimen'] = {"dir": "서북쪽 (乾宮)", "action": "생문(生門)을 찾아 윗사람에게 도움을 청하십시오.", "color": "Silver & Yellow"}
        elif my_char == '戊': 
            report['summary'] = {"keywords": ["문서취득", "학업성취", "마이웨이"], "score": 95, "desc": "용암이 굳어 산이 됩니다. 흔들리지 않는 기반을 마련하고 문서를 쥐게 됩니다."}
            report['wealth'] = "부동산 매매, 전세 계약 등 문서로 인한 목돈 운이 있습니다. 장기 투자가 유리합니다."
            report['career'] = "전문가 자격증을 따거나 학위를 받기에 최적입니다. 당신의 결재권이 강화됩니다."
            report['timing'] = "4월, 7월 (행운) / 1월 (주의)"
            report['qimen'] = {"dir": "중앙 및 사방", "action": "개문(開門)의 형국이니, 마음을 열고 널리 포용하십시오.", "color": "Brown & Beige"}
        elif my_char == '己': 
            report['summary'] = {"keywords": ["결실", "인정받음", "꼼꼼함"], "score": 90, "desc": "햇살이 밭을 비추니 곡식이 무르익습니다. 그동안의 노력이 보상받습니다."}
            report['wealth'] = "윗사람이나 모친의 도움으로 경제적 혜택을 입을 수 있습니다. 안전자산이 유리합니다."
            report['career'] = "기획 업무나 서류 업무에서 탁월한 성과를 냅니다. 꼼꼼함이 당신의 무기입니다."
            report['timing'] = "5월, 9월 (행운) / 2월 (주의)"
            report['qimen'] = {"dir": "남서쪽 (坤宮)", "action": "사문(死門)을 피해 안전한 곳에서 내실을 다지십시오.", "color": "Yellow & Ocher"}
        elif my_char == '庚': 
            report['summary'] = {"keywords": ["관살혼잡", "환골탈태", "압박감"], "score": 70, "desc": "불이 쇠를 녹여 도구를 만드는 시기입니다. 고통스럽지만 견디면 명검으로 태어납니다."}
            report['wealth'] = "돈보다는 명예를 쫓아야 돈이 따라옵니다. 편법을 쓰면 반드시 관재구설이 따릅니다."
            report['career'] = "업무량이 폭발적으로 늘어납니다. '나를 죽이지 못하는 고통은 나를 강하게 한다'를 기억하세요."
            report['timing'] = "8월, 11월 (행운) / 5월 (주의)"
            report['qimen'] = {"dir": "북쪽 (坎宮)", "action": "휴문(休門)의 지혜가 필요합니다. 물러서서 때를 기다리세요.", "color": "Black & White"}
        elif my_char == '辛': 
            report['summary'] = {"keywords": ["예민함", "정관운", "스트레스"], "score": 75, "desc": "보석이 불 옆에 있어 불안합니다. 빛을 비추면 더욱 반짝이니 시련 속에 기회가 있습니다."}
            report['wealth'] = "고정적인 수입이나 월급은 안정적이나, 투기성 자금은 위험합니다."
            report['career'] = "까다로운 상사를 만날 수 있습니다. 원칙대로만 처리하면 결국 인정받습니다."
            report['timing'] = "10월, 11월 (행운) / 5월 (주의)"
            report['qimen'] = {"dir": "북동쪽 (艮宮)", "action": "상문(傷門)을 조심하고, 보수적으로 움직이십시오.", "color": "White & Ivory"}
        elif my_char == '壬': 
            report['summary'] = {"keywords": ["수화기제", "재물대박", "역마살"], "score": 93, "desc": "큰 물이 큰 불을 만났습니다. 역동적인 변화 속에서 큰 재물을 취하는 대박의 기운입니다."}
            report['wealth'] = "2026년 가장 재물운이 좋은 시기입니다. 사업 확장, 무역 등 스케일 큰 돈이 오갑니다."
            report['career'] = "출장이 잦아지거나 부서 이동 등 변동수가 많습니다. 변화를 즐기면 기회가 됩니다."
            report['timing'] = "7월, 10월 (행운) / 1월 (주의)"
            report['qimen'] = {"dir": "동쪽 (震宮)", "action": "적극적으로 나아가 취하되, 뒤를 돌아보십시오.", "color": "Black & Blue"}
        elif my_char == '癸': 
            report['summary'] = {"keywords": ["천을귀인", "알짜배기", "현실적"], "score": 96, "desc": "가뭄에 단비가 내리는 격입니다. 2026년 최고의 길신 '천을귀인'이 당신을 돕습니다."}
            report['wealth'] = "뜻밖의 횡재수나 보너스가 기대됩니다. 실속 있는 알짜배기 투자가 유리합니다."
            report['career'] = "상사나 VIP 고객의 총애를 받습니다. 어려운 일도 주변의 도움으로 술술 풀립니다."
            report['timing'] = "8월, 9월 (행운) / 5월 (주의)"
            report['qimen'] = {"dir": "남쪽 (離宮)", "action": "귀인이 남쪽에서 옵니다. 밝은 곳으로 나아가십시오.", "color": "Black & Navy"}
        return report

    def calculate(self, year, month, day, hour, minute, gender, name="사용자"):
        try:
            kst_date = datetime.datetime(year, month, day, hour, minute)
        except ValueError: return None
        utc_date = kst_date - datetime.timedelta(hours=9)
        sun = ephem.Sun()
        sun.compute(utc_date, epoch=utc_date) 
        sun_lon = math.degrees(ephem.Ecliptic(sun).lon)
        if sun_lon < 0: sun_lon += 360
        target_year = year
        if month == 1: target_year = year - 1
        elif month == 2:
            if sun_lon < 315: target_year = year - 1
        year_gan = (target_year - 4) % 10
        year_ji = (target_year - 4) % 12
        temp_lon = sun_lon + 45
        if temp_lon >= 360: temp_lon -= 360
        month_idx = int(temp_lon / 30)
        month_start_map = {0: 2, 1: 4, 2: 6, 3: 8, 4: 0, 5: 2, 6: 4, 7: 6, 8: 8, 9: 0}
        month_gan = (month_start_map[year_gan % 5] + month_idx) % 10
        month_ji = (month_idx + 2) % 12 
        base_date = datetime.date(1900, 1, 1)
        target_date_only = datetime.date(year, month, day)
        diff_days = (target_date_only - base_date).days
        day_gan = (diff_days + 10) % 10
        day_ji = (diff_days + 10) % 12 
        total_min = hour * 60 + minute
        if total_min >= 23*60 + 30 or total_min < 1*60 + 30:
            time_ji = 0 
            if total_min >= 23*60 + 30: calc_day_gan = (day_gan + 1) % 10
            else: calc_day_gan = day_gan
        else:
            time_ji = ((total_min - 30) // 120 + 1) % 12
            calc_day_gan = day_gan
        time_start_map = {0: 0, 1: 2, 2: 4, 3: 6, 4: 8, 5: 0, 6: 2, 7: 4, 8: 6, 9: 8}
        time_gan = (time_start_map[calc_day_gan % 5] + time_ji) % 10

        gans = [year_gan, month_gan, day_gan, time_gan]
        jis = [year_ji, month_ji, day_ji, time_ji]
        titles = ["년주", "월주", "일주", "시주"]
        pillars = []
        for i in range(4):
            gan_char = self.cheon[gans[i]]
            ji_char = self.ji[jis[i]]
            sibsin = self._get_sibsin(day_gan, gans[i]) if i != 2 else "본원"
            unseong = self._get_12unseong(day_gan, jis[i])
            shinsal = self.get_shinsal(day_gan, day_ji, jis[i])
            sp1 = self.check_baekho(gans[i], jis[i])
            sp2 = self.check_goemigwan(gans[i], jis[i])
            pillars.append({
                "title": titles[i], "ganji": f"{gan_char}{ji_char}",
                "sibsin": sibsin, "unseong": unseong,
                "shinsal": shinsal, "special": f"{sp1} {sp2}".strip()
            })
        gongmang = self.get_gongmang(day_gan, day_ji)
        is_year_yang = (year_gan % 2 == 0)
        is_man = (gender == '남성')
        if (is_man and is_year_yang) or (not is_man and not is_year_yang):
            direction = 1
            dir_text = "순행"
        else:
            direction = -1
            dir_text = "역행"
        daewoon_num, debug_msg = self.get_daewoon_data(kst_date, direction)
        daewoon_list = []
        for i in range(1, 9):
            d_gan = (month_gan + i * direction) % 10
            d_ji = (month_ji + i * direction) % 12
            age = daewoon_num + (i-1) * 10
            daewoon_list.append(f"**{age}**<br>{self.cheon[d_gan]}{self.ji[d_ji]}")
        report_2026 = self.generate_detailed_report(day_gan, name)
        return {
            "pillars": pillars, "gongmang": gongmang, 
            "daewoon": {"dir": dir_text, "list": daewoon_list, "debug": debug_msg},
            "report_2026": report_2026,
            # 디버깅용: 정확히 어떤 날짜로 계산했는지 반환
            "input_check": f"양력 {year}년 {month}월 {day}일 {hour}시 {minute}분 ({gender})"
        }

# ==========================================
# 2. 스트림릿 UI (V40 - 무결성 검증)
# ==========================================
st.set_page_config(page_title="청은 오라클", page_icon="🐎", layout="wide")

st.markdown("""
<style>
    .report-card { background-color: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 20px; border-left: 5px solid #4e73df; }
    .card-title { font-size: 1.1em; font-weight: bold; color: #555; margin-bottom: 10px; }
    .keyword-badge { background-color: #e3f2fd; color: #1565c0; padding: 5px 10px; border-radius: 15px; font-size: 0.9em; font-weight: bold; margin-right: 5px; }
    .score-text { font-size: 2em; font-weight: bold; color: #2c3e50; }
    .highlight { color: #d63384; font-weight: bold; }
    .footer { text-align: center; color: #888; font-size: 0.8em; margin-top: 50px; }
    .debug-box { background-color: #fff3cd; color: #856404; padding: 10px; border-radius: 5px; font-size: 0.9em; margin-bottom: 20px; border: 1px solid #ffeeba; }
</style>
""", unsafe_allow_html=True)

st.title("🐎 청은(靑隱)의 2026 전략")
st.caption("청은기문명리연구소의 정통 명리학 알고리즘과 AI 오라클 엔진의 만남")
st.markdown("---")

with st.sidebar:
    st.header("📋 사용자 정보 입력")
    name_input = st.text_input("이름", "홍길동")
    b_date = st.date_input("생년월일", datetime.date(1990, 1, 1), min_value=datetime.date(1900,1,1))
    gender = st.radio("성별", ["남성", "여성"])
    b_time = st.time_input("태어난 시간", datetime.time(12, 0))
    cal_type = st.radio("양력/음력", ["양력", "음력(평달)", "음력(윤달)"])
    
    if st.button("운세 분석 시작", type="primary"):
        st.session_state['run'] = True

    st.markdown("---")
    st.subheader("👨‍🏫 연구소 정보")
    st.info("**소장:** 청은(靑隱) 선생\n**소속:** 청은기문명리연구소\n**시스템:** The Oracle V40 (Stable)")

if 'run' in st.session_state and st.session_state['run']:
    calendar = KoreanLunarCalendar()
    year, month, day = b_date.year, b_date.month, b_date.day
    
    # 음력 변환 로직 (변동 없음)
    if "음력" in cal_type:
        is_leap = "윤달" in cal_type
        calendar.setLunarDate(year, month, day, is_leap)
        year = calendar.solarYear
        month = calendar.solarMonth
        day = calendar.solarDay

    # ★ 캐싱된 함수 호출 (입력값 같으면 무조건 같은 결과 반환)
    result = calculate_saju_cached(year, month, day, b_time.hour, b_time.minute, gender, name_input)

    if result:
        # [0] 입력값 검증 (디버깅)
        st.markdown(f"<div class='debug-box'>✅ <strong>분석 기준일시 검증:</strong> {result['input_check']}</div>", unsafe_allow_html=True)

        # [1] 사주 원국
        st.subheader("1. 사주 원국 (Four Pillars)")
        cols = st.columns(4)
        for i, p in enumerate(reversed(result['pillars'])): 
            idx = 3 - i
            p = result['pillars'][idx]
            with cols[i]:
                st.markdown(f"""
                <div style='text-align:center; padding:15px; background-color:#f8f9fa; border-radius:10px; border:1px solid #ddd;'>
                    <strong>{p['title']}</strong><br>
                    <h2 style='margin:5px 0; color:#333;'>{p['ganji']}</h2>
                    <span style='color:grey; font-size:0.9em;'>{p['sibsin']}</span><br>
                    <span style='color:blue; font-size:0.9em;'>{p['unseong']}</span>
                </div>
                """, unsafe_allow_html=True)
                if p['shinsal'] != '-': st.caption(f"✨ {p['shinsal']}")

        st.markdown(f"<div style='margin-top:20px; font-weight:bold;'>🌀 대운 흐름 ({result['daewoon']['dir']})</div>", unsafe_allow_html=True)
        dw_cols = st.columns(8)
        for i, dw in enumerate(result['daewoon']['list']):
            with dw_cols[i]:
                st.markdown(f"<div style='text-align:center; border:1px solid #eee; border-radius:5px; padding:5px; font-size:0.8em;'>{dw}</div>", unsafe_allow_html=True)
        
        st.markdown("---")

        # [2] 2026 전략 리포트
        r = result['report_2026']
        st.subheader(f"2. {r['header']}")
        
        row1_col1, row1_col2 = st.columns([2, 1])
        with row1_col1:
            st.markdown(f"""
            <div class="report-card">
                <div class="card-title">🔑 올해의 핵심 키워드</div>
                <div style="margin-bottom:10px;">
                    {" ".join([f"<span class='keyword-badge'>{k}</span>" for k in r['summary']['keywords']])}
                </div>
                <p>{r['summary']['desc']}</p>
            </div>
            """, unsafe_allow_html=True)
        with row1_col2:
            st.markdown(f"""
            <div class="report-card" style="text-align:center;">
                <div class="card-title">🏆 종합 운세</div>
                <div class="score-text">{r['summary']['score']}점</div>
                <progress value="{r['summary']['score']}" max="100" style="width:100%"></progress>
            </div>
            """, unsafe_allow_html=True)

        row2_col1, row2_col2 = st.columns(2)
        with row2_col1:
            st.markdown(f"""
            <div class="report-card">
                <div class="card-title">💰 재물 & 투자 전략</div>
                {r['wealth']}
            </div>
            """, unsafe_allow_html=True)
        with row2_col2:
            st.markdown(f"""
            <div class="report-card">
                <div class="card-title">🏢 직업 & 커리어 전략</div>
                {r['career']}
            </div>
            """, unsafe_allow_html=True)

        row3_col1, row3_col2 = st.columns(2)
        with row3_col1:
            st.markdown(f"""
            <div class="report-card" style="border-left-color: #28a745;">
                <div class="card-title">📅 월별 운세 타이밍</div>
                {r['timing']}
            </div>
            """, unsafe_allow_html=True)
        with row3_col2:
            st.markdown(f"""
            <div class="report-card" style="border-left-color: #6610f2; background-color: #f3e5f5;">
                <div class="card-title">🧭 기문둔갑(奇門遁甲) 전략</div>
                <p><strong>📍 행운의 방위:</strong> <span class="highlight">{r['qimen']['dir']}</span></p>
                <p><strong>⚔️ 행동 지침:</strong> {r['qimen']['action']}</p>
                <p><strong>🍀 개운 컬러:</strong> {r['qimen']['color']}</p>
            </div>
            """, unsafe_allow_html=True)

    else:
        st.error("분석 중 오류가 발생했습니다.")
else:
    st.info("좌측 사이드바에 정보를 입력하고 '운세 분석 시작'을 눌러주세요.")

st.markdown("""
<div class="footer">
    © 2026 청은기문명리연구소 (Cheongeun Institute). All rights reserved. <br>
    Powered by AI Oracle Engine
</div>
""", unsafe_allow_html=True)