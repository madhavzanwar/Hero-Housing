"""The 12 synthetic FinPilot HomeLoan personas (all names, IDs, employers and banks are fictitious).

Consumed by `scripts/generate_personas.py`. Every number that ends up on a document is derived
from these specs deterministically, and the same values are written to `expected.json`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass
class Org:
    name: str            # legal name (letterhead)
    short: str           # how it appears in bank narrations
    address: str
    ifsc: str            # remitter IFSC (fictitious bank code)
    cin: str = ""
    tan: str = ""


@dataclass
class Bank:
    name: str
    branch: str
    ifsc: str
    account_no: str
    date_fmt: str = "%d/%m/%y"   # "%d/%m/%y" or "%d-%b-%Y"


@dataclass
class PropertySpec:
    address: str
    consideration: float          # agreement value / historical purchase price
    market_value: float
    area_sqft: float
    registration_no: str
    sro: str                      # sub-registrar office
    reg_date: date
    seller: str
    deed_type: str                # AGREEMENT_FOR_SALE | SALE_DEED | TITLE_DEED
    valuer: str
    description: str
    encumbrance: str = "NIL"


@dataclass
class Persona:
    pid: str
    title: str
    segment: str
    story: str
    expected_outcome: str
    acceptable_outcomes: list[str]
    # identity
    name_on_pan: str              # upper-case, as printed on PAN
    form_name: str                # as typed by the RM
    father: str
    dob: date
    gender: str
    pan: str
    aadhaar: str                  # 12 digits (only the last 4 are ever printed)
    address: str                  # one line, Aadhaar address
    city: str
    mobile: str
    # employment / income
    employment: str               # SALARIED | SELF_EMPLOYED
    org: Org
    designation: str = ""
    emp_id: str = ""
    doj: date | None = None
    target_net: float = 0.0       # salaried: approx monthly net pay
    pay_style: str = "corporate"  # corporate | govt
    pt: float = 200.0             # professional tax / month (state dependent)
    itr: list[tuple[str, float]] = field(default_factory=list)  # [(AY, total income)] for SE
    # application
    product: str = "HOME_LOAN"
    loan_amount: float = 0.0
    property_value: float = 0.0
    property_type: str = "RESIDENTIAL"
    tenure: int = 240
    purpose: str = "Purchase of residential flat"
    lap_end_use: str | None = None
    bureau: int = 760
    existing_emi: float = 0.0
    years_in_job: float = 5.0
    declared_income: float | None = None     # default = round(net, -3)
    co_applicant: dict[str, Any] | None = None
    is_first_home: bool = True
    # banking
    bank: Bank = field(default_factory=lambda: Bank("", "", "", ""))
    months: int = 6
    opening_balance: float = 150000.0
    emis: list[tuple[str, float, int]] = field(default_factory=list)  # (narration, amount, day)
    patterns: set[str] = field(default_factory=set)
    spend_level: float = 0.45     # share of income spent via UPI/cards/ATM
    # property
    prop: PropertySpec | None = None
    scans: set[str] = field(default_factory=set)
    forged: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


PERSONAS: list[Persona] = [
    Persona(
        pid="p01", title="Clean salaried IT engineer, Pune", segment="Salaried - Prime",
        story="Aarav, 32, is a senior software engineer at Acme Infotech with 6 years in the job. "
              "Buying his first 2BHK in Baner. Clean bureau, salary credited every month, no loans.",
        expected_outcome="APPROVE", acceptable_outcomes=["APPROVE"],
        name_on_pan="AARAV SUNIL DESHMUKH", form_name="Aarav Deshmukh", father="SUNIL DESHMUKH",
        dob=date(1994, 6, 18), gender="M", pan="BKRPD4821K", aadhaar="482917365524",
        address="Flat 12, Shantiniketan Society, Kothrud, Pune, Maharashtra 411038", city="Pune",
        mobile="9822014521", employment="SALARIED",
        org=Org("Acme Infotech Pvt Ltd", "ACME INFOTECH", "Tower 3, Hinjawadi Phase II, Pune 411057",
                "KTBK0000123", "U72900PN2011PTC139421", "PNEA14523F"),
        designation="Senior Software Engineer", emp_id="ACM10482", doj=date(2020, 7, 1),
        target_net=145000, pt=200, loan_amount=4500000, property_value=6200000, tenure=240,
        purpose="Purchase of residential flat", bureau=782, years_in_job=6.3,
        bank=Bank("Sahyadri Co-operative Bank", "Kothrud, Pune", "SHCB0000417", "41702010004521"),
        opening_balance=310000, spend_level=0.42,
        prop=PropertySpec(
            address="Flat No. 702, 7th Floor, B Wing, Sahyadri Heights, Survey No. 45/2, Baner, Pune 411045",
            consideration=6200000, market_value=6450000, area_sqft=980, registration_no="HVL-2/5821/2026",
            sro="Sub-Registrar Haveli No. 2, Pune", reg_date=date(2026, 10, 14),
            seller="Sahyadri Realty LLP", deed_type="AGREEMENT_FOR_SALE",
            valuer="Kulkarni & Sharma Valuers (Govt. Approved Valuer Reg. No. CAT-I/412/2014)",
            description="2BHK residential flat, RCC framed, ready possession"),
        scans={"valuation_report"},
    ),
    Persona(
        pid="p02", title="Govt teacher couple with co-applicant, Nagpur", segment="Salaried - Government",
        story="Sunita, 42, teaches at a government-aided school; husband Rajesh (also a teacher) is co-applicant. "
              "Buying a ready flat in Nagpur; LTV 84.6% within the 90% slab for loans up to Rs 30 lakh.",
        expected_outcome="APPROVE", acceptable_outcomes=["APPROVE"],
        name_on_pan="SUNITA RAJESH WANKHEDE", form_name="Sunita Wankhede", father="DATTATRAYA BHONDE",
        dob=date(1984, 2, 11), gender="F", pan="CQSPW6157M", aadhaar="739264018837",
        address="Plot 18, Gajanan Nagar, Wardha Road, Nagpur, Maharashtra 440015", city="Nagpur",
        mobile="9423117788", employment="SALARIED",
        org=Org("Vidarbha Shikshan Prasarak Mandal (Govt. Aided)", "VSPM NAGPUR",
                "Shankar Nagar, Nagpur 440010", "VTBK0000209", "", "NGPV02741C"),
        designation="Assistant Teacher (Grade II)", emp_id="VSPM-T-0918", doj=date(2009, 6, 15),
        target_net=52000, pay_style="govt", pt=200, loan_amount=2200000, property_value=2600000,
        tenure=192, bureau=771, years_in_job=17.4,
        co_applicant={"name": "Rajesh Wankhede", "relation": "Spouse", "monthly_net_income": 48000, "existing_emi": 0},
        bank=Bank("Vidarbha Trust Bank", "Wardha Road, Nagpur", "VTBK0000311", "31102000187733"),
        opening_balance=148000, spend_level=0.40,
        prop=PropertySpec(
            address="Flat No. 304, 3rd Floor, Gurukrupa Apartments, Mouza Somalwada, Wardha Road, Nagpur 440025",
            consideration=2600000, market_value=2680000, area_sqft=820, registration_no="NGP-4/3317/2026",
            sro="Sub-Registrar Nagpur Urban No. 4", reg_date=date(2026, 10, 9),
            seller="Shri Mohan Laxman Tidke", deed_type="AGREEMENT_FOR_SALE",
            valuer="Deshpande Associates (Govt. Approved Valuer Reg. No. CAT-I/233/2011)",
            description="2BHK residential flat in a 6-year-old building"),
        scans={"sale_deed"},
    ),
    Persona(
        pid="p03", title="Self-employed Chartered Accountant, Mumbai", segment="Self-employed Professional",
        story="Rohan, 43, runs his own CA practice for 14 years. Rs 1.1 Cr home loan on a Rs 1.6 Cr flat in Andheri "
              "(LTV 68.75%, under the 75% slab for loans above Rs 75 lakh). Two years of ITRs, steady client receipts.",
        expected_outcome="APPROVE", acceptable_outcomes=["APPROVE"],
        name_on_pan="ROHAN VIJAY MEHTA", form_name="Rohan Mehta", father="VIJAY MEHTA",
        dob=date(1983, 9, 5), gender="M", pan="AHMPM2290Q", aadhaar="618355902741",
        address="B-1104, Lokhandwala Residency, Andheri West, Mumbai, Maharashtra 400053", city="Mumbai",
        mobile="9820933410", employment="SELF_EMPLOYED",
        org=Org("R V Mehta & Associates, Chartered Accountants", "RV MEHTA ASSOC",
                "Office 7, Veera Desai Road, Andheri West, Mumbai 400058", "KCBK0000088"),
        itr=[("2025-26", 4210000), ("2026-27", 4815000)],
        loan_amount=11000000, property_value=16000000, tenure=240, bureau=801, years_in_job=14,
        declared_income=360000,
        bank=Bank("Konkan Coastal Bank", "Andheri West, Mumbai", "KCBK0000102", "10220400076610", "%d-%b-%Y"),
        months=12, opening_balance=1250000, spend_level=0.30,
        prop=PropertySpec(
            address="Flat No. 1802, 18th Floor, Tower A, Sea Breeze CHS, J P Road, Andheri West, Mumbai 400058",
            consideration=16000000, market_value=16400000, area_sqft=1150, registration_no="BDR-15/9087/2026",
            sro="Sub-Registrar Andheri No. 15, Mumbai Suburban", reg_date=date(2026, 10, 21),
            seller="Mrs. Farida Shabbir Lokhandwala", deed_type="AGREEMENT_FOR_SALE",
            valuer="Patil Engineers & Valuers (Govt. Approved Valuer Reg. No. CAT-I/098/2008)",
            description="3BHK residential flat with one covered car park"),
        scans={"valuation_report"},
    ),
    Persona(
        pid="p04", title="Kirana trader LAP for business expansion, Indore", segment="Self-employed Business - LAP",
        story="Ramesh, 51, has run a kirana & general store for 22 years. LAP of Rs 35 lakh against his shop-cum-house "
              "(Rs 70 lakh) to open a second outlet. Cash-heavy business: a few large counter-cash deposits.",
        expected_outcome="APPROVE_WITH_CONDITIONS", acceptable_outcomes=["APPROVE_WITH_CONDITIONS", "REFER"],
        name_on_pan="RAMESH KUMAR AGRAWAL", form_name="Ramesh Kumar Agrawal", father="GOPAL DAS AGRAWAL",
        dob=date(1975, 1, 22), gender="M", pan="AEPPA7741H", aadhaar="527740916382",
        address="42, Malharganj Main Road, Indore, Madhya Pradesh 452002", city="Indore",
        mobile="9826045512", employment="SELF_EMPLOYED",
        org=Org("Shree Ganesh Kirana & General Stores", "SHREE GANESH KIRANA",
                "42, Malharganj Main Road, Indore 452002", "MCBK0000045"),
        itr=[("2025-26", 1228000), ("2026-27", 1404000)],
        product="LAP", loan_amount=3500000, property_value=7000000, property_type="RESIDENTIAL",
        tenure=180, purpose="Loan against property", lap_end_use="Business expansion", bureau=742,
        years_in_job=22, declared_income=105000, is_first_home=False,
        bank=Bank("Malwa Commerce Bank", "Malharganj, Indore", "MCBK0000019", "01922100044518"),
        months=12, opening_balance=265000, patterns={"cash_business"}, spend_level=0.25,
        prop=PropertySpec(
            address="House No. 42, Malharganj Main Road, Ward 18, Indore 452002 (G+2, shop on ground floor)",
            consideration=1850000, market_value=7000000, area_sqft=1850, registration_no="IND-1/2214/2009",
            sro="Sub-Registrar Indore-1", reg_date=date(2009, 3, 17),
            seller="Shri Hukumchand Jain", deed_type="TITLE_DEED",
            valuer="Mahajan Technical Consultants (Govt. Approved Valuer Reg. No. CAT-I/551/2012)",
            description="Self-occupied residential house with ground-floor shop"),
        scans={"itr_2025-26"},
    ),
    Persona(
        pid="p05", title="Salaried with heavy existing EMIs (FOIR breach), Bengaluru", segment="Salaried - Prime",
        story="Karthik, 35, product manager. Already pays a car loan and a personal loan EMI; adding a Rs 60 lakh "
              "home loan pushes FOIR far above the 60% cap -> reduce amount / add co-applicant / close a loan.",
        expected_outcome="APPROVE_WITH_CONDITIONS", acceptable_outcomes=["APPROVE_WITH_CONDITIONS"],
        name_on_pan="KARTHIK RAMAN NAIR", form_name="Karthik Nair", father="RAMAN NAIR",
        dob=date(1990, 12, 3), gender="M", pan="BPLPN3308C", aadhaar="904418263370",
        address="No. 23, 4th Cross, HSR Layout Sector 2, Bengaluru, Karnataka 560102", city="Bengaluru",
        mobile="9886201133", employment="SALARIED",
        org=Org("Bluepeak Software Solutions Pvt Ltd", "BLUEPEAK SOFTWARE",
                "Embassy Tech Square Road, Bellandur, Bengaluru 560103", "CMBK0000301",
                "U72200KA2014PTC077312", "BLRB09981E"),
        designation="Product Manager", emp_id="BPS-22871", doj=date(2021, 4, 12),
        target_net=110000, pt=200, loan_amount=6000000, property_value=8500000, tenure=240, bureau=741,
        existing_emi=32700, years_in_job=5.5,
        bank=Bank("Coromandel Union Bank", "HSR Layout, Bengaluru", "CUBN0000702", "70210045532190", "%d-%b-%Y"),
        opening_balance=86000, spend_level=0.30,
        emis=[("ACH D- PRAGATI AUTO FINANCE LTD-CAR LOAN EMI", 18450, 5),
              ("NACH DR-SWIFTCASH CAPITAL-PERSONAL LOAN EMI", 14250, 7)],
        prop=PropertySpec(
            address="Flat No. B-905, Greenfields Meadows, Sarjapur Road, Bengaluru 560035",
            consideration=8500000, market_value=8650000, area_sqft=1240, registration_no="SJP-1/6610/2026",
            sro="Sub-Registrar Sarjapur", reg_date=date(2026, 10, 28),
            seller="Greenfields Developers Pvt Ltd", deed_type="SALE_DEED",
            valuer="Rao & Iyer Valuation Services (Govt. Approved Valuer Reg. No. CAT-I/305/2016)",
            description="3BHK residential apartment"),
        scans={"salary_slip_2026-08"},
    ),
    Persona(
        pid="p06", title="Borderline: bureau 680, NACH bounces, thin buffer, Hyderabad", segment="Salaried - Near prime",
        story="Srinivas, 39, operations executive at a logistics firm. Bureau 680, three EMI bounces in six months and "
              "a balance that hovers near zero before payday. Numbers just about work - an underwriter should decide.",
        expected_outcome="REFER", acceptable_outcomes=["REFER"],
        name_on_pan="SRINIVAS GOUD PALLAPU", form_name="Srinivas Goud Pallapu", father="NARSIMHA GOUD PALLAPU",
        dob=date(1987, 7, 29), gender="M", pan="CHRPP5521L", aadhaar="365019277412",
        address="H.No. 8-3-224, Yousufguda, Hyderabad, Telangana 500045", city="Hyderabad",
        mobile="9848077123", employment="SALARIED",
        org=Org("Deccan Freightlines Pvt Ltd", "DECCAN FREIGHTLINES", "Plot 44, IDA Uppal, Hyderabad 500039",
                "CMRB0000610", "U60231TG2008PTC058821", "HYDD07711B"),
        designation="Senior Executive - Operations", emp_id="DFL-4471", doj=date(2019, 2, 1),
        target_net=62000, pt=200, loan_amount=3200000, property_value=4200000, tenure=240, bureau=680,
        existing_emi=6000, years_in_job=7.8,
        bank=Bank("Charminar Mercantile Bank", "Ameerpet, Hyderabad", "CMRB0000233", "23301100098821"),
        opening_balance=24000, patterns={"bounces", "thin"}, spend_level=0.78,
        emis=[("ACH D- SWIFTRIDE FINANCE-TW LOAN EMI", 6000, 3)],
        prop=PropertySpec(
            address="Flat No. 207, Sai Residency, Kukatpally Housing Board Colony, Hyderabad 500072",
            consideration=4200000, market_value=4300000, area_sqft=1060, registration_no="KKP-3/7841/2026",
            sro="Sub-Registrar Kukatpally", reg_date=date(2026, 10, 30),
            seller="Shri K. Venkateswara Rao", deed_type="SALE_DEED",
            valuer="Sri Sai Valuers & Surveyors (Govt. Approved Valuer Reg. No. CAT-I/622/2015)",
            description="2BHK residential flat"),
        scans={"form16"},
    ),
    Persona(
        pid="p07", title="FRAUD: tampered salary slips, inflated income, Noida", segment="Salaried - Fraud",
        story="Nikhil declares Rs 1.8 lakh/month. His salary slips were edited in iLovePDF (net pay typed in a different "
              "font, round figures), but the bank shows a Rs 85k salary credit and Form 16 shows ~Rs 12 lakh a year.",
        expected_outcome="DECLINE", acceptable_outcomes=["DECLINE"],
        name_on_pan="NIKHIL ANAND VERMA", form_name="Nikhil Verma", father="ANAND PRAKASH VERMA",
        dob=date(1991, 4, 16), gender="M", pan="AXVPV9034D", aadhaar="811273645509",
        address="C-214, Sector 62, Noida, Uttar Pradesh 201309", city="Noida",
        mobile="9711334290", employment="SALARIED",
        org=Org("Zenith Retail Ventures Pvt Ltd", "ZENITH RETAIL", "Plot 9, Sector 18, Noida 201301",
                "YSBK0000877", "U52100UP2016PTC081234", "MRTZ03321A"),
        designation="Assistant Manager - Category", emp_id="ZRV-30915", doj=date(2022, 1, 10),
        target_net=85000, pt=0, loan_amount=7000000, property_value=9500000, tenure=240, bureau=731,
        years_in_job=4.8, declared_income=180000,
        bank=Bank("Yamuna Sahakari Bank", "Sector 62, Noida", "YSBK0000412", "41205500067321"),
        opening_balance=72000, patterns={"round"}, spend_level=0.55,
        prop=PropertySpec(
            address="Flat No. 1503, Tower C, Skyline Residency, Sector 150, Noida 201310",
            consideration=9500000, market_value=9600000, area_sqft=1450, registration_no="NDA-2/11893/2026",
            sro="Sub-Registrar Sadar, Gautam Buddh Nagar", reg_date=date(2026, 11, 2),
            seller="Skyline Infra Developers Pvt Ltd", deed_type="SALE_DEED",
            valuer="Bansal Valuation Consultants (Govt. Approved Valuer Reg. No. CAT-I/719/2017)",
            description="3BHK residential apartment"),
        scans={"valuation_report"}, forged=True,
        extra={"forged_net": 180000.0, "forged_gross": 200000.0},
    ),
    Persona(
        pid="p08", title="Age 54, 25-year tenure ask, 95% LTV, low income, Jaipur", segment="Salaried - Decline",
        story="Prakash, 54, mill supervisor, wants Rs 28.5 lakh over 25 years on a Rs 30 lakh flat. Retirement at 60 caps "
              "tenure at ~5.5 years, LTV is 95% and income of ~Rs 38k cannot carry the EMI.",
        expected_outcome="DECLINE", acceptable_outcomes=["DECLINE"],
        name_on_pan="PRAKASH CHAND JOSHI", form_name="Prakash Chand Joshi", father="RAM CHAND JOSHI",
        dob=date(1972, 5, 10), gender="M", pan="AFJPJ1176R", aadhaar="290156637481",
        address="77, Shastri Nagar, Jaipur, Rajasthan 302016", city="Jaipur",
        mobile="9414022871", employment="SALARIED",
        org=Org("Rajputana Spinning Mills Ltd", "RAJPUTANA SPINNING", "RIICO Industrial Area, Sitapura, Jaipur 302022",
                "MRBK0000150", "L17111RJ1988PLC004512", "JPRR01188D"),
        designation="Shift Supervisor", emp_id="RSM-1187", doj=date(1998, 8, 1),
        target_net=38000, pt=0, loan_amount=2850000, property_value=3000000, tenure=300, bureau=712,
        years_in_job=28, is_first_home=True,
        bank=Bank("Marudhar Rural Bank", "Shastri Nagar, Jaipur", "MRBK0000088", "08810200034417"),
        opening_balance=41000, spend_level=0.62,
        prop=PropertySpec(
            address="Flat No. G-3, Ganpati Enclave, Jhotwara Road, Jaipur 302012",
            consideration=3000000, market_value=3050000, area_sqft=760, registration_no="JPR-2/4410/2026",
            sro="Sub-Registrar Jaipur-II", reg_date=date(2026, 10, 26),
            seller="Shri Bhanwar Lal Sharma", deed_type="SALE_DEED",
            valuer="Mathur Valuers (Govt. Approved Valuer Reg. No. CAT-I/188/2010)",
            description="2BHK ground-floor residential flat"),
        scans={"sale_deed"},
    ),
    Persona(
        pid="p09", title="LAP for doctor's clinic on commercial property, Chennai", segment="Self-employed Professional - LAP",
        story="Dr Lakshmi, 48, runs a multispeciality clinic. LAP of Rs 80 lakh against her Rs 1.5 Cr commercial premises "
              "(LTV 53%, within the 55% commercial cap) to buy diagnostic equipment. Strong ITRs, digital receipts.",
        expected_outcome="APPROVE", acceptable_outcomes=["APPROVE"],
        name_on_pan="LAKSHMI SUBRAMANIAN", form_name="Dr Lakshmi Subramanian", father="SUBRAMANIAN KRISHNAMURTHY",
        dob=date(1978, 8, 30), gender="F", pan="ALKPS6603N", aadhaar="773018452296",
        address="12, Second Main Road, Gandhi Nagar, Adyar, Chennai, Tamil Nadu 600020", city="Chennai",
        mobile="9840112278", employment="SELF_EMPLOYED",
        org=Org("Sri Lakshmi Multispeciality Clinic", "SRI LAKSHMI CLINIC",
                "48, LB Road, Thiruvanmiyur, Chennai 600041", "CUBN0000415"),
        itr=[("2025-26", 3890000), ("2026-27", 4260000)],
        product="LAP", loan_amount=8000000, property_value=15000000, property_type="COMMERCIAL", tenure=180,
        purpose="Loan against property", lap_end_use="Business expansion", bureau=812, years_in_job=16,
        declared_income=315000, is_first_home=False,
        bank=Bank("Coromandel Union Bank", "Adyar, Chennai", "CUBN0000415", "41510077009321", "%d-%b-%Y"),
        months=12, opening_balance=1480000, patterns={"clinic"}, spend_level=0.28,
        prop=PropertySpec(
            address="Ground & First Floor, No. 48, LB Road, Thiruvanmiyur, Chennai 600041",
            consideration=6200000, market_value=15000000, area_sqft=2400, registration_no="ADR-1/1876/2012",
            sro="Sub-Registrar Adyar", reg_date=date(2012, 6, 8),
            seller="M/s Kumaran Constructions", deed_type="TITLE_DEED",
            valuer="Venkat & Co. Chartered Engineers (Govt. Approved Valuer Reg. No. CAT-I/277/2009)",
            description="Commercial premises used as a clinic (G+1)"),
        scans={"itr_2025-26", "valuation_report"},
    ),
    Persona(
        pid="p10", title="LAP for stock-market investment + gambling spends, Delhi", segment="Self-employed Business - LAP",
        story="Gaurav, 40, auto-parts trader, wants LAP for 'capital market investment' - a prohibited end use. "
              "His statement shows frequent Dream11 / rummy / betting app debits.",
        expected_outcome="DECLINE", acceptable_outcomes=["DECLINE", "REFER"],
        name_on_pan="GAURAV MALHOTRA", form_name="Gaurav Malhotra", father="SURINDER MALHOTRA",
        dob=date(1985, 11, 19), gender="M", pan="BGMPM8812J", aadhaar="645590128743",
        address="H-34, Rajouri Garden, New Delhi, Delhi 110027", city="New Delhi",
        mobile="9810556621", employment="SELF_EMPLOYED",
        org=Org("Malhotra Auto Spares", "MALHOTRA AUTO", "Shop 112, Kashmere Gate Auto Market, Delhi 110006",
                "ISBK0000231"),
        itr=[("2025-26", 1655000), ("2026-27", 1802000)],
        product="LAP", loan_amount=4000000, property_value=7500000, property_type="RESIDENTIAL", tenure=180,
        purpose="Loan against property", lap_end_use="Capital market investment", bureau=724, years_in_job=12,
        declared_income=140000, is_first_home=False,
        bank=Bank("Indraprastha Sahakari Bank", "Rajouri Garden, New Delhi", "ISBK0000108", "10810300052276"),
        months=12, opening_balance=420000, patterns={"gambling", "trader"}, spend_level=0.35,
        prop=PropertySpec(
            address="H-34, Second Floor, Rajouri Garden, New Delhi 110027",
            consideration=3100000, market_value=7500000, area_sqft=1350, registration_no="DL-WEST/8812/2015",
            sro="Sub-Registrar II, Janakpuri (West Delhi)", reg_date=date(2015, 9, 2),
            seller="Smt. Kamlesh Arora", deed_type="TITLE_DEED",
            valuer="Khanna Valuers & Engineers (Govt. Approved Valuer Reg. No. CAT-I/834/2013)",
            description="Residential builder floor (second floor)"),
        scans={"sale_deed"},
    ),
    Persona(
        pid="p11", title="Returning NRI - negative-list (PEP) name match, Mumbai", segment="Salaried - EDD",
        story="Vikram, 47, returned from Dubai to head advisory at a Mumbai firm. Financially strong, but his name "
              "matches a politically exposed person on the screening list -> enhanced due diligence by a human.",
        expected_outcome="REFER", acceptable_outcomes=["REFER"],
        name_on_pan="VIKRAM RATHORE SINGHANIA", form_name="Vikram Rathore Singhania", father="DEVENDRA SINGHANIA",
        dob=date(1979, 3, 14), gender="M", pan="AFWPS7319K", aadhaar="318840276615",
        address="Flat 2101, Seaview Heights, Worli Sea Face, Mumbai, Maharashtra 400018", city="Mumbai",
        mobile="9930441187", employment="SALARIED",
        org=Org("Westbridge Capital Advisors Pvt Ltd", "WESTBRIDGE CAPITAL", "Level 9, BKC One, Bandra Kurla Complex, Mumbai 400051",
                "KCBK0000215", "U67190MH2017PTC291177", "MUMW22817G"),
        designation="Managing Director - Advisory", emp_id="WCA-0007", doj=date(2023, 4, 3),
        target_net=320000, pt=200, loan_amount=15000000, property_value=24000000, tenure=240, bureau=788,
        years_in_job=3.6,
        bank=Bank("Konkan Coastal Bank", "Worli, Mumbai", "KCBK0000144", "14420800091145", "%d-%b-%Y"),
        opening_balance=2150000, spend_level=0.35,
        prop=PropertySpec(
            address="Flat No. 3401, 34th Floor, Tower 2, Marine Crest, Prabhadevi, Mumbai 400025",
            consideration=24000000, market_value=24500000, area_sqft=1620, registration_no="BBY-3/14277/2026",
            sro="Sub-Registrar Mumbai City No. 3", reg_date=date(2026, 10, 19),
            seller="Marine Crest Realtors Pvt Ltd", deed_type="AGREEMENT_FOR_SALE",
            valuer="Shah & Gokhale Valuers (Govt. Approved Valuer Reg. No. CAT-I/041/2005)",
            description="3BHK luxury residential apartment"),
        scans={"salary_slip_2026-10"},
    ),
    Persona(
        pid="p12", title="Young first-home buyer, LTV just over 90%, Ahmedabad", segment="Salaried - First home",
        story="Priya, 26, data analyst. Rs 28 lakh on a Rs 31 lakh flat = LTV 90.3%, just above the 90% regulatory cap "
              "-> approve at Rs 27.9 lakh (reduce amount).",
        expected_outcome="APPROVE_WITH_CONDITIONS", acceptable_outcomes=["APPROVE_WITH_CONDITIONS"],
        name_on_pan="PRIYA HIREN PATEL", form_name="Priya Patel", father="HIREN PATEL",
        dob=date(2000, 1, 26), gender="F", pan="DKTPP2047B", aadhaar="556201983347",
        address="14, Shivalik Bungalows, Satellite, Ahmedabad, Gujarat 380015", city="Ahmedabad",
        mobile="9727045563", employment="SALARIED",
        org=Org("Sabarmati Fintech Labs Pvt Ltd", "SABARMATI FINTECH", "GIFT City Tower 2, Gandhinagar 382355",
                "SPBK0000077", "U72900GJ2019PTC109961", "AHMS11742C"),
        designation="Data Analyst", emp_id="SFL-1290", doj=date(2022, 8, 1),
        target_net=68000, pt=200, loan_amount=2800000, property_value=3100000, tenure=300, bureau=752,
        years_in_job=4.3,
        bank=Bank("Sabarmati People's Bank", "Satellite, Ahmedabad", "SPBK0000132", "13200400066218"),
        opening_balance=118000, spend_level=0.45,
        prop=PropertySpec(
            address="Flat No. A-602, Shaligram Lakeview, Vastrapur, Ahmedabad 380015",
            consideration=3100000, market_value=3150000, area_sqft=690, registration_no="AHD-8/7390/2026",
            sro="Sub-Registrar Ahmedabad-8 (Vastrapur)", reg_date=date(2026, 10, 24),
            seller="Shaligram Infracon LLP", deed_type="SALE_DEED",
            valuer="Trivedi & Desai Valuers (Govt. Approved Valuer Reg. No. CAT-I/366/2018)",
            description="2BHK residential flat"),
        scans={"form16", "valuation_report"},
    ),
]
