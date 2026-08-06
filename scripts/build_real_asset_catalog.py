#!/usr/bin/env python3
"""Build the checked-in Virginia real-asset catalog from public sources."""

import csv
import io
import json
import urllib.parse
import urllib.request
import zipfile
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "virginia_real_assets.json"
CATALOG_DATE = "2026-08-06"

FAA_LAYER = (
    "https://services6.arcgis.com/ssFJjBXIUyZDrSYZ/ArcGIS/rest/services/US_Airport/FeatureServer/0"
)
DOAV_DIRECTORY = "https://doav.virginia.gov/airport-directory/"
DOAV_SPONSOR_DIRECTORY = "https://doav.virginia.gov/airport_sponsors/"
FACTBOOK = (
    "https://www.vada.virginia.gov/media/governorvirginiagov/"
    "secretary-of-veterans-and-defense-affairs/pdf/VA-FactBook_WEB_2020-10-19-CSG.pdf"
)
VEDP_UXS = "https://www.vedp.org/industry/unmanned-systems"
VEDP_COMPANIES = "https://www.vedp.org/news/home-business-more-400-years"
VIPC_CENTER = "https://vipc.org/initiatives/virginia-unmanned-systems-center/"
VIPC_TEST = (
    "https://vipc.org/virginia-launches-advanced-air-mobility-and-unmanned-"
    "systems-test-site-program/"
)
PORT_CAPABILITIES = "https://www.portofvirginia.com/gateway/capabilities/"
IPEDS_DIRECTORY_ZIP = "https://nces.ed.gov/ipeds/datacenter/data/HD2024.zip"
IPEDS_DIRECTORY_PAGE = "https://nces.ed.gov/ipeds/datacenter/DataFiles.aspx"
REGION_BOUNDARIES = ROOT / "static" / "data" / "virginia-regions.geojson"
CONTACT_ENRICHMENT_PATH = ROOT / "data" / "asset_contact_enrichment.json"

IPEDS_NAME_ALIASES = {
    "University of Virginia-Main Campus": "University of Virginia",
    "Virginia Polytechnic Institute and State University": "Virginia Tech",
}
REGION_FEATURES = json.loads(REGION_BOUNDARIES.read_text())["features"]
CONTACT_ENRICHMENT = (
    json.loads(CONTACT_ENRICHMENT_PATH.read_text()).get("assets", {})
    if CONTACT_ENRICHMENT_PATH.exists()
    else {}
)

SOURCES = {
    "vedp": ("VEDP: Unmanned Systems in Virginia", VEDP_UXS),
    "vedp_contact": (
        "Virginia Economic Development Partnership contact information",
        "https://www.vedp.org/contact-us",
    ),
    "vedp_companies": ("VEDP: Virginia Unmanned Systems Companies", VEDP_COMPANIES),
    "vipc": ("Virginia Unmanned Systems Center", VIPC_CENTER),
    "vipc_test": ("Virginia AAM and Unmanned Systems Test Site Program", VIPC_TEST),
    "port": ("Port of Virginia Capabilities", PORT_CAPABILITIES),
    "vt_keas": (
        "Virginia Tech Kentland Experimental Aerial Systems Laboratory",
        "https://autonomyandrobotics.centers.vt.edu/groups/keas.html",
    ),
    "vt_acsl": (
        "Virginia Tech Advanced Control Systems Lab",
        "https://www.ise.vt.edu/research/labs/advanced-control-systems-lab.html",
    ),
    "vt_marine": (
        "Virginia Tech Center for Marine Autonomy and Robotics",
        "https://marinerobotics.centers.vt.edu/index.html",
    ),
    "vt_autoboat": ("AutoBoat at Virginia Tech", "https://autoboat.aoe.vt.edu/"),
    "uva_robotics": (
        "UVA Robotics and Autonomous Systems",
        "https://www.engineering.virginia.edu/labs-groups/link-lab/research/"
        "robotics-and-autonomous-systems",
    ),
    "uva_maye": (
        "UVA Robotics, Dynamics, and Autonomous Systems",
        "https://engineering.virginia.edu/department/mechanical-and-aerospace-"
        "engineering/research/robotics-dynamics-and-autonomous-systems",
    ),
    "uva_ece": (
        "UVA Robotics and Embedded Systems",
        "https://engineering.virginia.edu/department/electrical-and-computer-"
        "engineering/robotics-and-embedded-systems",
    ),
    "vcu_arvl": ("VCU Autonomous Robots and Vehicles Laboratory", "https://arvl.lab.vcu.edu/"),
    "vt_made": (
        "Virginia Tech Robotics and Autonomy",
        "https://made.vt.edu/robotics-autonomy.html",
    ),
    "vt_aav": (
        "Autonomous Aerial Vehicles at Virginia Tech",
        "https://www.vtaav.org/our-team",
    ),
    "vt_spacedrones": (
        "Virginia Tech SpaceDrones Laboratory",
        "https://spacedrones.aoe.vt.edu/",
    ),
    "vt_mission_systems": (
        "Virginia Tech Mission Systems Division",
        "https://nationalsecurity.vt.edu/research/mission-systems-division.html",
    ),
    "vt_idpro": (
        "Virginia Tech IDPro Projects",
        "https://idpro.icat.vt.edu/projects.html",
    ),
    "nasa_certain": (
        "NASA Langley Drone Flying Site",
        "https://www.nasa.gov/centers-and-facilities/langley/"
        "nasa-langley-drone-flying-site-open-for-testing/",
    ),
    "vccs_brcc": (
        "VCCS: Unmanned Systems Courses at Blue Ridge Community College",
        "https://courses.vccs.edu/colleges/brcc/courses/UMS-UnmannedSystems",
    ),
    "vccs_brightpoint": (
        "VCCS: Unmanned Systems Courses at Brightpoint Community College",
        "https://courses.vccs.edu/colleges/jtcc/courses/UMS-UnmannedSystems",
    ),
    "vccs_danville": (
        "VCCS: Unmanned Systems Courses at Danville Community College",
        "https://courses.vccs.edu/colleges/dcc/courses/UMS-UnmannedSystems",
    ),
    "vccs_escc": (
        "VCCS: Unmanned Systems Courses at Eastern Shore Community College",
        "https://courses.vccs.edu/colleges/escc/courses/UMS-UnmannedSystems",
    ),
    "vccs_laurel": (
        "VCCS: Unmanned Systems Courses at Laurel Ridge Community College",
        "https://courses.vccs.edu/colleges/lfcc/courses/UMS-UnmannedSystems",
    ),
    "vccs_mountain_gateway": (
        "VCCS: Unmanned Systems Courses at Mountain Gateway Community College",
        "https://courses.vccs.edu/colleges/dslcc/courses/UMS-UnmannedSystems",
    ),
    "vccs_tcc": (
        "VCCS: Unmanned Systems Courses at Tidewater Community College",
        "https://courses.vccs.edu/colleges/tcc/courses/UMS-UnmannedSystems",
    ),
    "vhcc_suas": (
        "Virginia Highlands Community College Small UAS Certificate",
        "https://www.vhcc.edu/small-unmanned-aerial-systems-suas",
    ),
    "vpcc_drone": (
        "Virginia Peninsula Community College Drone Flight Technician",
        "https://www.vpcc.edu/program/small-unmanned-aircraft-systems-drone-flight-technician/",
    ),
    "vccs_system": (
        "Virginia Community College System Unmanned Systems Courses",
        "https://courses.vccs.edu/courses/UMS-UnmannedSystems",
    ),
    "vwcc_autonomous": (
        "Virginia Western Autonomous Vehicle Technology",
        "https://www.virginiawestern.edu/academics/mechatronics/autonomous-vehicle-technology/",
    ),
    "vsp_uas": (
        "Virginia State Police Department History",
        "https://vsp.virginia.gov/about-us/department-history/",
    ),
    "dwr_uas": (
        "Virginia Conservation Police 2024 Annual Report",
        "https://dwr.virginia.gov/wp-content/uploads/media/Virginia-Conservation-Police-Annual-Report-2024.pdf",
    ),
    "dof_uas": (
        "Virginia Department of Forestry Drone Program",
        "https://dof.virginia.gov/user_directory/jason-a-braunstein/",
    ),
    "dcjs_drone": (
        "DCJS Unmanned Aircraft Trade and Replace Program",
        "https://www.dcjs.virginia.gov/grants/programs/cy-26-unmanned-aircraft-trade-and-replace-program",
    ),
    "doav_aam": (
        "Virginia Department of Aviation Advanced Air Mobility",
        "https://doav.virginia.gov/advanced_air_mobility/",
    ),
    "virginia_fix": (
        "Virginia Department of Aviation Flight Information Exchange",
        "https://doav.virginia.gov/aviation_programs_resources/",
    ),
    "stafford_aam": (
        "Stafford-Warrenton-Winchester AAM Integration Project",
        "https://doav.virginia.gov/wp-content/uploads/Files/DocumentLibrary/"
        "Stafford_Warrenton_Winchester_Project.pdf",
    ),
    "mitre_range": (
        "MITRE National Range",
        "https://www.mitre.org/news-insights/fact-sheet/mitre-national-range",
    ),
    "go_virginia": (
        "GO Virginia",
        "https://www.dhcd.virginia.gov/gova",
    ),
    "hampton_roads_alliance": (
        "Hampton Roads Alliance autonomous-systems opportunity assessment",
        "https://hamptonroadsalliance.com/wp-content/uploads/2025/01/"
        "Alliance-Board-Deck-September.pdf",
    ),
    "shd_tech_park": (
        "Shenandoah Valley Aviation Technology Park",
        "https://cspdc.org/2023/11/27/shd-aviation-tech-park-holds-ribbon-cutting/",
    ),
    "shd_tech_park_site": (
        "Shenandoah Valley Aviation Technology Park site development",
        "https://cspdc.org/2023/06/07/"
        "shenandoah-valley-aviation-technology-park-hangars-near-completion/",
    ),
    "hii_uxs": (
        "HII Unmanned Systems Center of Excellence",
        "https://www.hii.com/news/unmanned-systems-center-of-excellence",
    ),
    "longbow": (
        "City of Hampton: Hampton Roads Autonomy Demonstrations",
        "https://www.hampton.gov/CivicAlerts.aspx?AID=4973&ARC=10333",
    ),
    "aac": ("Advanced Aircraft Company", "https://advancedaircraftcompany.com/"),
    "adaptive": ("Adaptive Aerospace Group", "https://adaptiveaero.com/"),
    "rapidflight": (
        "RapidFlight Manassas UAS Manufacturing Headquarters",
        "https://www.prnewswire.com/news-releases/rapidflight-celebrates-grand-opening-of-uas-3d-manufacturing-headquarters-in-manassas-virginia-301884344.html",
    ),
    "xelevate": (
        "Xelevate Leesburg Unmanned Systems Facility",
        "https://xelevateus.com/leesburg-virginia/",
    ),
    "virginia_uas": ("Virginia UAS", "https://virginiauas.com/"),
    "aerovironment": ("AeroVironment", "https://www.avinc.com/domains/"),
    "qinetiq": ("QinetiQ US locations", "https://www.qinetiq.com/en-us/who-we-are/our-locations"),
    "dedrone": ("Dedrone by Axon", "https://www.dedrone.com/about/contact-us"),
    "vt_grain_drones": (
        "Virginia Tech Grain Crop Drone Research",
        "https://www.pubs.ext.vt.edu/content/pubs_ext_vt_edu/en/SPES/spes-747.html",
    ),
    "vt_esarec_drones": (
        "Virginia Tech Eastern Shore AREC Drone Research",
        "https://www.arec.vaes.vt.edu/content/dam/arec_vaes_vt_edu/eastern-shore/newsletter/The%20Stalk%20-%20July%202024.pdf",
    ),
    "vt_counter_uas": (
        "Virginia Tech Counter UAS Research and Testing Center",
        "https://news.vt.edu/articles/2025/04/research-counteruascenter.html",
    ),
    "vt_usl": (
        "Virginia Tech Uncrewed Systems Laboratory",
        "https://usl.me.vt.edu/projects.html",
    ),
    "fairfax_county_uas": (
        "Fairfax County Unmanned Aircraft Systems",
        "https://www.fairfaxcounty.gov/uas/",
    ),
    "gmu_police_uas": (
        "George Mason University Police UAS Flight Log",
        "https://police.gmu.edu/records-and-reporting/uas-drone-flight-log/",
    ),
    "gmu_starship": (
        "George Mason Starship Robot Delivery Service",
        "https://abs.gmu.edu/services/dining/transition-updates/",
    ),
    "gmu_sparx": (
        "George Mason Controls and Robotics Research",
        "https://electrical.gmu.edu/research/controls-and-robotics",
    ),
    "gmu_mico": (
        "George Mason Multi-agent Intelligence, Control, and Optimization Lab",
        "https://mason.gmu.edu/~xwang64/",
    ),
    "gmu_robotixx": (
        "George Mason RobotiXX Laboratory",
        "https://people.cs.gmu.edu/~xxiao2/index.html",
    ),
    "gmu_mix": (
        "Mason Innovation Exchange Short Course Programs",
        "https://www.mix.gmu.edu/mix-short-course-programs",
    ),
    "gmu_c5i_dfr": (
        "George Mason C5I Northern Virginia DFR Study",
        "https://c5i.gmu.edu/2025/10/c5i-center-leads-drone-as-a-first-responder-study-for-northern-virginia/",
    ),
    "virginia_beach_uas": (
        "CISA: City of Virginia Beach UAS Emergency Operations Program",
        "https://www.cisa.gov/sites/default/files/2024-08/24_0826_necp_spotlight_implementing_uas_programs_to_support_emergency_operations_final_508C.pdf",
    ),
    "fairfax_city_uas": (
        "City of Fairfax Police Annual Report",
        "https://www.fairfaxva.gov/files/assets/city/v/1/police/documents/annual-reports/fy2023-ffx-pd-annual-report.pdf",
    ),
    "vsgc_drone_academies": (
        "Virginia Space Grant Consortium GeoTED-UAS Drone Academies",
        "https://vsgc.odu.edu/geoted-uas/",
    ),
    "vcu_uas": (
        "Virginia Commonwealth University Unmanned Aircraft System",
        "https://healthsafety.vcu.edu/operational-risk/unmanned-aircraft-system/",
    ),
    "uva_uas": (
        "University of Virginia Unmanned Aircraft Systems Operations",
        "https://uvaemergency.virginia.edu/unmanned-aircraft-uas/operating-uas-uva",
    ),
    "uva_crc_uas": (
        "UVA Coastal Research Center Drone Pilot Compliance Checklist",
        "https://abcrc.virginia.edu/files/abcrc/files/coastal_research_center___drone_pilot_compliance_checklist.pdf",
    ),
    "heven": ("Heven AeroTech", "https://hevenaerotech.com/"),
    "agricision": ("Agricision", "https://www.agricisioninc.com/"),
    "blue_ridge_defense": ("Blue Ridge Defense Works", "https://blueridgedefense.com/"),
    "zenith": (
        "Zenith Aerotech",
        "https://zenithaerotech.com/about-us-tethered-drone/",
    ),
    "odu_uas": (
        "Old Dominion University UAS/Drone Operation",
        "https://www.odu.edu/risk-management/advisories/uas-drones",
    ),
    "vsu_uas": (
        "Virginia State University Use of Unmanned Aerial Systems Policy",
        "https://www.vsu.edu/files/docs/policies/8000/use-unmanned-aerial-systems-drones.pdf",
    ),
    "prince_edward_uas": (
        "Prince Edward County Drone Program",
        "https://www.co.prince-edward.va.us/News-Article/Pyle-Named-County-Emergency-Management-Coordinator",
    ),
    "accomack_uas": (
        "Accomack County DPS Safety Education Day",
        "https://www.co.accomack.va.us/Home/Components/News/News/381/18",
    ),
    "campbell_uas": (
        "Campbell County Sheriff's Office 2024 Annual Report",
        "https://www.campbellcountyva.gov/324/Annual-Reports",
    ),
    "university_vt": ("Virginia Tech: About", "https://www.vt.edu/about.html"),
    "university_uva": ("University of Virginia: About UVA", "https://www.virginia.edu/about-uva/"),
    "university_vcu": ("Virginia Commonwealth University: About", "https://www.vcu.edu/about-vcu/"),
    "university_odu": ("Old Dominion University: About", "https://www.odu.edu/about"),
    "university_cnu": ("Christopher Newport University", "https://cnu.edu/"),
    "university_gmu": ("George Mason University: Key Facts", "https://www.gmu.edu/about/key-facts"),
    "university_jmu": ("James Madison University: About", "https://www.jmu.edu/about/index.shtml"),
    "university_liberty": ("Liberty University: About", "https://www.liberty.edu/about/"),
    "university_vsu": ("Virginia State University: About", "https://www.vsu.edu/about/"),
    "university_wm": ("William & Mary: About", "https://www.wm.edu/about/"),
    "university_hampton": ("Hampton University", "https://home.hamptonu.edu/"),
    "hampton_uas": (
        "Hampton University Uncrewed Aircraft Systems",
        "https://home.hamptonu.edu/engineering/uas/",
    ),
    "university_radford": ("Radford University: About", "https://www.radford.edu/about/"),
    "radford_uas": (
        "Radford University Unmanned Aerial Systems Courses",
        "https://www.radford.edu/registrar/course-descriptions/unmanned-aerial-systems/index.html",
    ),
    "university_vmi": ("Virginia Military Institute: About", "https://www.vmi.edu/about/"),
    "vmi_counter_uas": (
        "VMI Cadet Drone Detection Research",
        "https://www.vmi.edu/news/headlines/2025-2026/drone-detection-focus-of-cadet-research.php",
    ),
    "university_nsu": ("Norfolk State University", "https://www.nsu.edu/About"),
    "nsu_tactical_autonomy": (
        "Norfolk State Tactical Autonomy Research Program",
        "https://www.nsu.edu/News/2023/February/CSET-Good-News-Report-Jan-2023",
    ),
    "nsu_drone_course": (
        "Norfolk State University Drone Photography Course",
        "https://catalog.nsu.edu/undergraduate/course-descriptions/fia/fia.pdf",
    ),
    "university_shenandoah": ("Shenandoah University: About", "https://www.su.edu/about/"),
    "shenandoah_drone_vr": (
        "Shenandoah Drone Assembly Virtual-Reality Training",
        "https://www.su.edu/blog/2023/06/12/shenandoah-vr-faculty-students-creating-drone-assembly-training-program/",
    ),
    "university_longwood": ("Longwood University: About", "https://www.longwood.edu/about/"),
    "longwood_seed": (
        "Longwood SEED Autonomous Marine Project",
        "https://www.longwood.edu/news/2026/seed-entrepreneurship-experience/",
    ),
    "university_ehc": ("Emory & Henry University: About", "https://www.ehc.edu/about/"),
    "ehc_drone": ("Emory & Henry Drone Pilot Test Preparation", "https://catalog.ehc.edu/envs-330"),
    "university_rbc": ("Richard Bland College", "https://www.rbc.edu/"),
    "university_uvawise": (
        "University of Virginia's College at Wise",
        "https://www.uvawise.edu/about",
    ),
    "uvawise_streamwise": (
        "UVA Wise STREAMWISE Robotics and Drone Programs",
        "https://www.uvawise.edu/news/2025/10/empowering-next-generation-innovators-through-streamwise",
    ),
    "rbc_uas_certificate": (
        "Richard Bland College Programs and Degrees",
        "https://www.rbc.edu/academics/programs-degree/",
    ),
    "rbc_uas_center": (
        "Richard Bland College Energy-Centric UAS Center",
        "https://www.rbc.edu/news-releases/rbc-will-serve-as-operations-site-for-uas-center/",
    ),
    "vcu_robotics_degree": (
        "VCU Robotics and Autonomous Systems Engineering Degree",
        "https://news.vcu.edu/article/vcu-to-offer-new-undergraduate-degree-in-robotics-and-autonomous-systems-engineering",
    ),
    "liberty_medium_uas": (
        "Liberty University Medium UAS Certificate",
        "https://www.liberty.edu/aeronautics/certificates/medium-unmanned-aerial-systems/",
    ),
    "liberty_uas_experience": (
        "Liberty University UAS Operational Experience",
        "https://www.liberty.edu/aeronautics/uas-operational-experience/",
    ),
    "nci": ("New College Institute", "https://newcollegeinstitute.org/"),
    "ialr_agbot": (
        "IALR Precision Agriculture Areas of Focus",
        "https://www.ialr.org/plant-endophyte-research-center/areas-of-focus/",
    ),
    "swva_drone_soccer": (
        "Southwest Virginia Higher Education Center Board Minutes",
        "https://www.swcenter.edu/wp-content/uploads/2025/07/2024Dec12_Minutes_FINAL.pdf",
    ),
    "go_tec": (
        "Institute for Advanced Learning and Research GO TEC",
        "https://www.ialr.org/go-tec/",
    ),
    "harrowgate_drone_park": (
        "Chesterfield County Parks and Facilities",
        "https://www.chesterfield.gov/163/Parks-and-Facilities",
    ),
    "fulcrum": ("Fulcrum Concepts Contact", "https://fulcrumconceptsllc.com/contact/"),
    "anra": ("VEDP: Organizing the Skies", "https://www.vedp.org/news/organizing-skies"),
    "auterion": (
        "Auterion Moves Corporate Headquarters to Arlington",
        "https://auterion.com/auterion-moves-corporate-headquarters-to-arlington-virginia/",
    ),
    "flying_ship": ("Flying Ship Company", "https://www.flyingship.co/contact"),
    "sentinel": (
        "NAVAIR Small Business Profile: Sentinel Robotic Solutions",
        "https://www.navair.navy.mil/osbp/node/11301",
    ),
    "autonomous_flight": (
        "Autonomous Flight Technologies",
        "https://www.autonomousflight.us/company",
    ),
    "ici_usv": (
        "ICI Services Unmanned Surface Vehicle Development",
        "https://icisrvcs.com/news/2020/2/5/236/ici-services-to-support-navy-unmanned-surface-vehicle-development/index.html",
    ),
    "ccals": (
        "Commonwealth Center for Advanced Logistics Systems",
        "https://www.ccals.com/",
    ),
    "spotsylvania_uas": (
        "Spotsylvania Regional Public Safety UAS Program",
        "https://www.spotsylvania.va.us/DocumentCenter/View/20535/May-19-2022---No-Quorum",
    ),
    "norfolk_police_uas": (
        "Norfolk Crime Reduction Strategies Report",
        "https://www.norfolk.gov/DocumentCenter/View/73566/CMO-Crime-Reduction-Strategies-Report_Final-Draft?bidId=",
    ),
    "norfolk_harbor_uas": (
        "Norfolk Harbor Patrol Unit",
        "https://www.norfolk.gov/6644/Harbor-Patrol-Unit",
    ),
    "montgomery_uas": (
        "Montgomery County Sheriff's Office Support Services",
        "https://www.montgomerycountyva.gov/1/departments-services/sheriffs-office/support-services",
    ),
    "roanoke_police_uas": (
        "Roanoke County Police Department Special Operations",
        "https://www.roanokecountyva.gov/DocumentCenter/View/1061/Agenda-with-Reports",
    ),
    "roanoke_fire_uas": (
        "Roanoke County Community Strategic Plan Annual Report",
        "https://www.roanokecountyva.gov/DocumentCenter/View/22361/2021-Community-Strategic-Plan-Annual-Report",
    ),
    "winchester_uas": (
        "Winchester Emergency Management UAS Program",
        "https://www.winchesterva.gov/files/assets/public/v/1/finance/fy23_budget_book.pdf",
    ),
    "danville_uas": (
        "Danville Life Saving Crew Drone Operations",
        "https://www.dlsc.org/drones",
    ),
    "leesburg_uas": (
        "Leesburg Police Unmanned Aircraft Systems Team",
        "https://www.leesburgva.gov/departments/police/about-the-lpd/investigations-operational-support-bureau/specialty-units/unmaned-aircraft-systems-uas-team",
    ),
    "fredericksburg_uas": (
        "Fredericksburg Police Unmanned Aircraft System Team",
        "https://www.fredericksburgva.gov/1529/Unmanned-Aircraft-System-Team",
    ),
    "fredericksburg_dfr": (
        "Fredericksburg Drone as First Responder Program",
        "https://www.fredericksburgva.gov/2066/Drone-as-First-Responder-DFR-Program",
    ),
    "augusta_uas": (
        "Augusta County Sheriff's Office Drone Team",
        "https://www.co.augusta.va.us/home/showpublisheddocument/20491/639101430011700000",
    ),
    "bedford_uas": (
        "Bedford County Sheriff's Office Drone Team",
        "https://sheriff.bedfordcountyva.gov/Home/Components/News/News/1947/3987?arch=1&npage=2",
    ),
    "charlottesville_uas": (
        "Charlottesville Police Emergency Services Unit",
        "https://www.charlottesville.gov/1697/Emergency-Services-Unit",
    ),
    "york_rover": ("York County ROVER Team", "https://www.yorkcounty.gov/1874/The-ROVER-Team"),
    "mecklenburg_uas": (
        "Mecklenburg County Sheriff's Office",
        "https://www.mecklenburgva.com/194/Sheriffs-Office",
    ),
    "newport_news_uas": (
        "Newport News Police and Fire Drone Unit",
        "https://www.nnva.gov/2394/Drone-Unit",
    ),
    "prince_william_uas": (
        "Prince William County Police sUAS Team",
        "https://www.pwcva.gov/news/pwcpd-spotlight-departments-suas-team-serving-sky/",
    ),
    "chesterfield_dfr": (
        "Chesterfield County Police",
        "https://www.chesterfield.gov/941/Police",
    ),
    "chesterfield_fire_uas": (
        "Chesterfield Fire and EMS Community Risk Assessment",
        "https://www.chesterfield.gov/DocumentCenter/View/46569/Chesterfield-Fire-and-EMS-Community-Risk-Assessment-and-Standards-of-Cover-PDF",
    ),
    "henrico_robotics": (
        "Henrico Fire Specialty Teams",
        "https://henrico.gov/fire/about-us/specialty-teams/",
    ),
    "arlington_uas": (
        "Arlington Joint Public Safety UAS Program",
        "https://www.arlingtonva.us/Government/Departments/PSCEM/Unmanned-Aircraft-Systems",
    ),
    "albemarle_police_uas": (
        "Albemarle County Adopted Budget",
        "https://www.albemarle.org/home/showpublisheddocument/26848/638869823368570000",
    ),
    "albemarle_fire_uas": (
        "Albemarle County Fire Rescue Staffing Study",
        "https://www.albemarle.org/home/showpublisheddocument/27911/638961259487630000",
    ),
    "loudoun_uas": (
        "Loudoun County Sheriff's Office Drone Capability",
        "https://sheriff.loudoun.gov/m/newsflash/home/detail/9418",
    ),
    "lynchburg_fire_uas": (
        "Lynchburg Fire Department Annual Report",
        "https://www.lynchburgva.gov/ArchiveCenter/ViewFile/Item/64",
    ),
    "lynchburg_police_uas": (
        "Lynchburg Police Drone Unit",
        "https://lynchburgva.gov/DocumentCenter/View/4331",
    ),
    "harrisonburg_uas": (
        "Harrisonburg Police Special Weapons and Tactics Team",
        "https://www.harrisonburgva.gov/SWAT",
    ),
    "suffolk_uas": (
        "Suffolk Police UAS Unit",
        "https://www.suffolkva.us/directory.aspx?EID=60",
    ),
    "richmond_police_uas": (
        "Richmond Police Small Unmanned Aerial Vehicle Policy",
        "https://rva.gov/sites/default/files/2024-02/GO%2006-32%20Unmanned%20Aerial%20Vehicle.pdf",
    ),
    "james_city_dfr": (
        "James City County Police Drone as First Responder Program",
        "https://www.jamescitycountyva.gov/m/newsflash/Home/Detail/6334",
    ),
    "hanover_uas": (
        "Hanover County Sheriff's Office sUAS Team",
        "https://www.hanoversheriff.com/412/sUAS-Team",
    ),
    "culpeper_uas": (
        "Culpeper Police Department FY2025 Annual Report",
        "https://files.culpeperva.gov/FY25%20TOC%20Annual%20Report.pdf",
    ),
    "orange_uas": (
        "Louisa County: Orange County Drone Team Deployment",
        "https://www.louisacounty.gov/m/newsflash?cat=22%2C1",
    ),
    "auvsi_ridge": (
        "AUVSI Ridge and Valley Chapter",
        "https://www.auvsiridgeandvalley.org/",
    ),
    "nswc_dahlgren": (
        "NSWC Dahlgren Division: What We Do",
        "https://www.navsea.navy.mil/Home/Warfare-Centers/NSWC-Dahlgren/What-We-Do/",
    ),
    "dahlgren_autonomy_lab": (
        "NSWC Dahlgren Outdoor Autonomy Laboratory",
        "https://www.navsea.navy.mil/Media/News/Article-View/Article/3886620/maximizing-resources-building-a-competitive-outdoor-autonomy-lab-environment/",
    ),
    "carderock_ccd": (
        "NSWC Carderock Combatant Craft Division",
        "https://www.navsea.navy.mil/Home/Warfare-Centers/NSWC-Carderock/Who-We-Are/Norfolk-Virginia/",
    ),
    "mcwl": (
        "Marine Corps Warfighting Laboratory Autonomous Reconnaissance",
        "https://www.marines.mil/News/News-Display/Article/746745/marine-corps-warfighting-lab-tests-autonomous-reconnaissance/",
    ),
    "dcjs_awards": (
        "DCJS CY 2026 Unmanned Aircraft Trade and Replace Awards",
        "https://www.vaco.org/wp-content/uploads/2025/12/DCJS-Meeting-UAB-Chart.pdf",
    ),
    "caroline_uas": (
        "Caroline County Fire and Rescue UAS Grant Authorization",
        "https://co.caroline.va.us/AgendaCenter/ViewFile/Item/7378?fileID=11595",
    ),
    "gloucester_uas": (
        "Gloucester County Sheriff's Office UAS Grant Award",
        "https://pub-gloucesterva.escribemeetings.com/filestream.ashx?DocumentId=24451",
    ),
    "colonial_heights_uas": (
        "Colonial Heights FY2026 Drone Replacement Appropriation",
        "https://colonialheightsva.gov/AgendaCenter/ViewFile/Agenda/_02102026-750?packet=true",
    ),
    "hampton_joint_uas": (
        "Hampton Police and Fire UAS Policy",
        "https://www.hampton.gov/DocumentCenter/View/37936/557-UAS-Unmanned-Aerial-System-PDF",
    ),
    "henry_uas": (
        "Henry County Sheriff's Office Drone Replacement Grant",
        "https://www.henrycountyva.gov/AgendaCenter/ViewFile/Agenda/_01272026-344",
    ),
    "hopewell_uas": (
        "Hopewell Fire and EMS Operations",
        "https://www.hopewellva.gov/510/Operations",
    ),
    "king_george_uas": (
        "King George County Public Safety Drone Program",
        "https://www.kinggeorgecountyva.gov/AgendaCenter/ViewFile/Minutes/_02032026-1454",
    ),
    "stafford_uas": (
        "Stafford County Sheriff's Office Field Operations",
        "https://www.staffordsheriff.com/content/about/fieldoperations.cfm",
    ),
    "frederick_uas": (
        "Frederick County Sheriff's Office Special Operations",
        "https://www.fcva.us/departments/sheriff-s-office/divisions/special-operations",
    ),
    "powhatan_uas": (
        "Powhatan County Emergency Operations Plan",
        "https://www.powhatanva.gov/DocumentCenter/View/8410/Emergency-Operations-Plan-2024",
    ),
    "chesapeake_uas": (
        "Chesapeake Police Operations Bureau",
        "https://www.cityofchesapeake.net/921/Operations-Bureau",
    ),
    "newport_news_dfr": (
        "Newport News Drones as First Responders",
        "https://www.nnva.gov/3269/Drones-as-First-Responders",
    ),
    "odu_iacs": (
        "ODU Institute for Autonomous and Connected Systems",
        "https://www.odu.edu/iacs",
    ),
    "odu_minor": (
        "ODU Uncrewed Systems Design and Development Minor",
        "https://www.odu.edu/academics/programs/minor/uncrewed-systems-design-development",
    ),
    "odu_masts": (
        "ODU Maritime Autonomous Systems Test Site",
        "https://www.odu.edu/article/beyond-boats-and-submarines-odu-city-of-norfolk-celebrate-the-opening-of-the-maritime",
    ),
    "vims_c4po": (
        "VIMS Collaboratory for Physical Oceanography",
        "https://www.vims.edu/research/units/labgroups/c4po/",
    ),
    "vims_asl": (
        "VIMS Autonomous Systems Laboratory",
        "https://www.vims.edu/people/patterson_mr/",
    ),
    "vims_hab": (
        "VIMS Harmful Algal Bloom Technology",
        "https://www.vims.edu/bayinfo/habs/tech/",
    ),
    "blue_vigil": (
        "Blue Vigil Autonomous Aerial Lighting",
        "https://www.bluevigil.com/about",
    ),
    "p1_technologies": (
        "P1 Technologies Roanoke Manufacturing",
        "https://www.p1tec.com/",
    ),
    "vedp_keltech": (
        "VEDP: Blue Vigil Tether Manufacturing in Roanoke County",
        "https://www.vedp.org/news/industries-future-unmanned-systems",
    ),
    "smart_testbed": (
        "Virginia Smart Community Testbed Projects",
        "https://vatestbed.com/projects",
    ),
    "space_authority": (
        "Virginia Spaceport Authority Facilities",
        "https://www.vaspace.org/our-facilities",
    ),
    "nasa_roam": (
        "NASA Langley ROAM UAS Operations Center",
        "https://csaob.larc.nasa.gov/roam/",
    ),
    "wallops_research_park": (
        "Accomack County: Wallops Research Park Background and Timeline",
        "https://www.accomack.gov/614/Background-Timeline",
    ),
    "wallops_research_park_location": (
        "NASA Wallops Research Park Environmental Assessment",
        "https://www.nasa.gov/wp-content/uploads/2024/10/wallops-research-park-fea-fonsi.pdf",
    ),
    "dam_neck_activity": (
        "NSWCDD Dam Neck Activity",
        "https://www.navsea.navy.mil/Home/Warfare-Centers/NSWC-Dahlgren/Dam-Neck/",
    ),
    "talsa_east": (
        "NAVAIR: Navy TALSA East Small UAS Training Facility",
        "https://www.navair.navy.mil/news/Navy-opens-doors-first-small-unmanned-aircraft-systems-training-facility/Tue-08022022-0923",
    ),
    "marine_counter_drone_team": (
        "Marine Corps Counter-Drone Team",
        "https://www.tecom.marines.mil/In-the-News/Stories/News-Article-Display/Article/4538355/tecom-establishes-marine-corps-robotics-integration-group-and-counter-drone-team/",
    ),
    "fairfax_dfr": (
        "Fairfax County Police DFR Transparency",
        "https://www.fairfaxcounty.gov/police/real-time-crime-center-transparency",
    ),
    "charles_city_uas": (
        "Virginia Sheriffs' Association: Charles City Drone Operations Team",
        "https://vasheriff.org/2025/03/05/charles-city-county-sheriffs-office-announces-formation-of-drone-operations-team/",
    ),
    "bedford_fire_uas": (
        "Bedford Fire Department 2018 Annual Report",
        "https://bedfordva.gov/DocumentCenter/View/1970/BFD-Annual-Report-2018-PDF",
    ),
    "bedford_fire_drone_replacement": (
        "Bedford Town Council 2022 Drone Replacement Minutes",
        "https://www.bedfordva.gov/AgendaCenter/ViewFile/Minutes/_08232022-258",
    ),
    "mag_aerospace": (
        "MAG Aerospace Corporate Headquarters",
        "https://www.magaero.com/connect/",
    ),
    "inertial_labs": (
        "Inertial Labs Headquarters and R&D",
        "https://inertiallabs.com/inertial-labs-inc/",
    ),
    "dzyne": (
        "DZYNE Technologies",
        "https://dzyne.com/about/",
    ),
    "dzyne_location": (
        "U.S. SBIR Portfolio: DZYNE Technologies",
        "https://www.sbir.gov/portfolio/406214",
    ),
    "ensco": (
        "ENSCO Capabilities",
        "https://www.ensco.com/capabilities",
    ),
    "ensco_location": (
        "ENSCO Locations",
        "https://www.ensco.com/contact/locations",
    ),
    "scout_space": (
        "Scout Space",
        "https://www.scout.space/",
    ),
    "scout_space_location": (
        "U.S. SBIR Portfolio: Scout Space",
        "https://www.sbir.gov/portfolio/1543541",
    ),
    "usi": (
        "Universal Solutions International",
        "https://usi-inc.com/",
    ),
    "leidos_autonomy": (
        "Leidos Multi-Domain Autonomy",
        "https://investors.leidos.com/node/35791/pdf",
    ),
    "leidos_location": (
        "Leidos Investor FAQs",
        "https://investors.leidos.com/stockholder-resources/investor-faqs",
    ),
    "caci_counter_uas": (
        "CACI Counter-UAS",
        "https://www.caci.com/",
    ),
    "parsons_counter_uas": (
        "Parsons Counter-UAS Solutions",
        "https://www.parsons.com/2026/06/parsons-cuas-solutions-strengthen-national-security-and-protect-critical-infrastructure/",
    ),
    "parsons_location": (
        "Parsons Corporate Office Locations",
        "https://www.parsons.com/contact-us/",
    ),
    "eagle_aviation": (
        "Eagle Aviation Technologies",
        "https://eagleaviationtech.com/about-us-1",
    ),
    "aircommerce_park": (
        "Newport News EDA: Patrick Henry Corridor and AirCommerce Park",
        "https://newportnewsva.com/business-neighborhoods/patrick-henry-corridor/",
    ),
    "aircommerce_uas": (
        "Newport News Aerospace and Aviation Assets",
        "https://newportnewsva.com/wp-content/uploads/2022/07/NNEDA-Aerospace-Aviation-Flyer.pdf",
    ),
}

PROFILES = {
    "research_air": {
        "categories": ["Research and technical depth", "Test and operational environments"],
        "domains": ["Unmanned aircraft systems", "Cross-domain autonomy"],
        "capabilities": [
            "Autonomy and artificial intelligence",
            "Testing, evaluation, verification, and validation",
        ],
        "missions": ["Training and experimentation"],
        "relevance": (
            "Provides documented research, engineering, or test capacity for aerial and "
            "cross-domain autonomous systems."
        ),
    },
    "research_ground": {
        "categories": ["Research and technical depth", "Multi-domain missions"],
        "domains": ["Ground vehicles and robotics", "Cross-domain autonomy"],
        "capabilities": [
            "Autonomy and artificial intelligence",
            "Perception, sensing, and sensor fusion",
        ],
        "missions": ["Training and experimentation"],
        "relevance": (
            "Develops robotics, perception, planning, control, or connected-vehicle capabilities "
            "that support autonomous ground and cross-domain systems."
        ),
    },
    "research_marine": {
        "categories": ["Research and technical depth", "Test and operational environments"],
        "domains": ["Maritime surface systems", "Undersea systems"],
        "capabilities": [
            "Autonomy and artificial intelligence",
            "Navigation and positioning",
            "Perception, sensing, and sensor fusion",
        ],
        "missions": ["Maritime domain awareness", "Environmental monitoring"],
        "relevance": (
            "Provides documented marine robotics, autonomy, sensing, navigation, or field-test "
            "capacity for surface and undersea systems."
        ),
    },
    "research_cross": {
        "categories": ["Research and technical depth", "Test and operational environments"],
        "domains": [
            "Unmanned aircraft systems",
            "Ground vehicles and robotics",
            "Maritime surface systems",
            "Undersea systems",
            "Cross-domain autonomy",
        ],
        "capabilities": [
            "Autonomy and artificial intelligence",
            "Systems engineering and integration",
            "Testing, evaluation, verification, and validation",
        ],
        "missions": ["Training and experimentation"],
        "relevance": (
            "Provides documented cross-domain autonomy research, engineering, prototyping, "
            "simulation, or field-test capacity."
        ),
    },
    "workforce": {
        "categories": ["Workforce and talent"],
        "domains": ["Unmanned aircraft systems", "Cross-domain autonomy"],
        "capabilities": [
            "Operations, maintenance, and sustainment",
            "Systems engineering and integration",
        ],
        "missions": ["Training and experimentation"],
        "relevance": (
            "Builds a documented education or credential pathway for unmanned-systems operators, "
            "maintainers, engineers, or technicians."
        ),
    },
    "workforce_robotics": {
        "categories": ["Workforce and talent"],
        "domains": [
            "Unmanned aircraft systems",
            "Ground vehicles and robotics",
            "Cross-domain autonomy",
        ],
        "capabilities": [
            "Autonomy and artificial intelligence",
            "Systems engineering and integration",
            "Manufacturing, materials, and prototyping",
        ],
        "missions": ["Training and experimentation"],
        "relevance": (
            "Builds a documented education or experiential-learning pathway in autonomous "
            "vehicles, robotics, uncrewed aircraft, sensing, integration, or prototyping."
        ),
    },
    "company_air": {
        "categories": ["Companies and solution providers"],
        "domains": ["Unmanned aircraft systems"],
        "capabilities": [
            "Systems engineering and integration",
            "Operations, maintenance, and sustainment",
        ],
        "missions": ["Infrastructure inspection", "Logistics and contested logistics"],
        "relevance": "Provides documented UAS technology, aircraft, services, integration, or operations.",
    },
    "company_ground": {
        "categories": ["Companies and solution providers"],
        "domains": ["Ground vehicles and robotics"],
        "capabilities": [
            "Autonomy and artificial intelligence",
            "Systems engineering and integration",
        ],
        "missions": ["Logistics and contested logistics"],
        "relevance": "Develops or integrates documented autonomous-ground-vehicle technology.",
    },
    "company_marine": {
        "categories": ["Companies and solution providers", "Manufacturing and supply chain"],
        "domains": ["Maritime surface systems", "Undersea systems"],
        "capabilities": [
            "Systems engineering and integration",
            "Manufacturing, materials, and prototyping",
        ],
        "missions": ["Maritime domain awareness"],
        "relevance": "Provides maritime engineering, shipbuilding, integration, or robotic-system capacity.",
    },
    "state": {
        "categories": ["State strategy and coordination", "Programs and initiatives"],
        "domains": ["Cross-domain autonomy"],
        "capabilities": ["Safety, policy, regulatory, and airspace integration"],
        "missions": ["Training and experimentation"],
        "relevance": "Coordinates, funds, regulates, or accelerates Virginia's unmanned-systems ecosystem.",
    },
    "aam_program": {
        "categories": ["State strategy and coordination", "Programs and initiatives"],
        "domains": ["Advanced Air Mobility", "Unmanned aircraft systems"],
        "capabilities": [
            "Safety, policy, regulatory, and airspace integration",
            "Data engineering, analytics, and edge computing",
        ],
        "missions": ["Logistics and contested logistics", "Training and experimentation"],
        "relevance": (
            "Supports documented planning, infrastructure integration, information exchange, "
            "or operational enablement for advanced air mobility and uncrewed aviation."
        ),
    },
    "economic_development": {
        "categories": [
            "State strategy and coordination",
            "Programs and initiatives",
            "Manufacturing and supply chain",
        ],
        "domains": ["Cross-domain autonomy"],
        "capabilities": [
            "Systems engineering and integration",
            "Manufacturing, materials, and prototyping",
        ],
        "missions": ["Training and experimentation"],
        "relevance": (
            "Provides documented economic-development coordination, business attraction, "
            "funding, site support, or partnership development relevant to Virginia's autonomy "
            "ecosystem."
        ),
    },
    "port": {
        "categories": ["Physical infrastructure and logistics"],
        "domains": ["Maritime surface systems", "Cross-domain autonomy"],
        "capabilities": [
            "Operations, maintenance, and sustainment",
            "Data engineering, analytics, and edge computing",
        ],
        "missions": ["Logistics and contested logistics", "Infrastructure inspection"],
        "relevance": (
            "Provides port, intermodal, staging, or semi-automated logistics infrastructure relevant "
            "to maritime autonomy, inspection, and deployment."
        ),
    },
    "enabling": {
        "categories": ["Research and technical depth", "Manufacturing and supply chain"],
        "domains": ["Cross-domain autonomy"],
        "capabilities": [
            "Manufacturing, materials, and prototyping",
            "Systems engineering and integration",
        ],
        "missions": ["Training and experimentation"],
        "relevance": (
            "Provides advanced manufacturing, modeling, sensing, communications, or prototyping "
            "capacity that enables unmanned-system development and scale-up."
        ),
    },
    "company_cross": {
        "categories": ["Companies and solution providers", "Manufacturing and supply chain"],
        "domains": [
            "Unmanned aircraft systems",
            "Ground vehicles and robotics",
            "Cross-domain autonomy",
        ],
        "capabilities": [
            "Autonomy and artificial intelligence",
            "Systems engineering and integration",
            "Manufacturing, materials, and prototyping",
        ],
        "missions": ["Training and experimentation"],
        "relevance": (
            "Develops, integrates, manufactures, or supports documented autonomous and uncrewed "
            "systems across one or more operating domains."
        ),
    },
    "test_multi": {
        "categories": ["Test and operational environments", "Companies and solution providers"],
        "domains": [
            "Unmanned aircraft systems",
            "Ground vehicles and robotics",
            "Maritime surface systems",
        ],
        "capabilities": [
            "Testing, evaluation, verification, and validation",
            "Systems engineering and integration",
        ],
        "missions": ["Training and experimentation"],
        "relevance": (
            "Provides a publicly documented environment for unmanned-system testing, training, "
            "demonstration, validation, or operational integration."
        ),
    },
    "national_range": {
        "categories": [
            "Test and operational environments",
            "Research and technical depth",
            "Federal and defense customer access",
        ],
        "domains": [
            "Unmanned aircraft systems",
            "Counter-UAS",
            "Ground vehicles and robotics",
        ],
        "capabilities": [
            "Testing, evaluation, verification, and validation",
            "Systems engineering and integration",
            "Navigation and positioning",
        ],
        "missions": [
            "Training and experimentation",
            "Public safety and emergency response",
            "Counter-UAS",
        ],
        "relevance": (
            "Provides a documented controlled environment for testing, evaluating, and "
            "prototyping uncrewed aircraft, counter-UAS, ground systems, and communications."
        ),
    },
    "aam_test": {
        "categories": [
            "Test and operational environments",
            "Physical infrastructure and logistics",
            "Programs and initiatives",
        ],
        "domains": ["Advanced Air Mobility", "Unmanned aircraft systems"],
        "capabilities": [
            "Testing, evaluation, verification, and validation",
            "Safety, policy, regulatory, and airspace integration",
            "Operations, maintenance, and sustainment",
        ],
        "missions": ["Training and experimentation", "Logistics and contested logistics"],
        "relevance": (
            "Supports documented testing or operational integration of uncrewed aviation and "
            "advanced-air-mobility concepts in the National Airspace System."
        ),
    },
    "public_safety": {
        "categories": ["Programs and initiatives", "Multi-domain missions"],
        "domains": ["Unmanned aircraft systems"],
        "capabilities": [
            "Operations, maintenance, and sustainment",
            "Perception, sensing, and sensor fusion",
        ],
        "missions": [
            "Public safety and emergency response",
            "Search and rescue",
            "Surveying and mapping",
        ],
        "relevance": (
            "Operates, coordinates, or funds a documented public-sector UAS capability for "
            "emergency response, mapping, inspection, conservation, or public safety."
        ),
    },
    "agriculture": {
        "categories": ["Research and technical depth", "Programs and initiatives"],
        "domains": ["Unmanned aircraft systems"],
        "capabilities": [
            "Perception, sensing, and sensor fusion",
            "Data engineering, analytics, and edge computing",
        ],
        "missions": ["Agriculture and natural resources", "Environmental monitoring"],
        "relevance": (
            "Conducts documented drone-based sensing, imaging, analysis, or field research for "
            "agriculture, natural resources, or environmental monitoring."
        ),
    },
    "institutional_uas": {
        "categories": ["Research and technical depth", "Programs and initiatives"],
        "domains": ["Unmanned aircraft systems"],
        "capabilities": [
            "Safety, policy, regulatory, and airspace integration",
            "Operations, maintenance, and sustainment",
        ],
        "missions": ["Training and experimentation"],
        "relevance": (
            "Operates a documented institutional UAS program supporting research, instruction, "
            "and compliant flight operations."
        ),
    },
    "counter_uas_research": {
        "categories": ["Research and technical depth", "Test and operational environments"],
        "domains": ["Counter-UAS", "Unmanned aircraft systems"],
        "capabilities": [
            "Perception, sensing, and sensor fusion",
            "Testing, evaluation, verification, and validation",
        ],
        "missions": ["Counter-UAS", "Force protection and installation security"],
        "relevance": (
            "Provides documented counter-UAS research, testing, and evaluation capabilities."
        ),
    },
    "company_counter_uas": {
        "categories": ["Companies and solution providers", "Manufacturing and supply chain"],
        "domains": ["Counter-UAS", "Unmanned aircraft systems"],
        "capabilities": [
            "Systems engineering and integration",
            "Manufacturing, materials, and prototyping",
        ],
        "missions": ["Counter-UAS", "Force protection and installation security"],
        "relevance": "Develops documented counter-UAS systems, components, or production capacity.",
    },
    "company_agriculture": {
        "categories": ["Companies and solution providers", "Manufacturing and supply chain"],
        "domains": ["Unmanned aircraft systems"],
        "capabilities": [
            "Perception, sensing, and sensor fusion",
            "Manufacturing, materials, and prototyping",
        ],
        "missions": ["Agriculture and natural resources"],
        "relevance": "Provides documented agricultural UAS platforms, software, or related services.",
    },
    "federal_autonomy": {
        "categories": [
            "Federal and defense customer access",
            "Test and operational environments",
            "Research and technical depth",
        ],
        "domains": [
            "Unmanned aircraft systems",
            "Ground vehicles and robotics",
            "Maritime surface systems",
            "Undersea systems",
        ],
        "capabilities": [
            "Autonomy and artificial intelligence",
            "Systems engineering and integration",
            "Testing, evaluation, verification, and validation",
        ],
        "missions": [
            "Training and experimentation",
            "Force protection and installation security",
        ],
        "relevance": (
            "Provides publicly documented federal research, experimentation, engineering, or "
            "test capacity for autonomous and uncrewed systems."
        ),
    },
    "federal_training_air": {
        "categories": ["Federal and defense customer access", "Workforce and talent"],
        "domains": ["Unmanned aircraft systems"],
        "capabilities": [
            "Operations, maintenance, and sustainment",
            "Systems engineering and integration",
        ],
        "missions": ["Training and experimentation", "Force protection and installation security"],
        "relevance": (
            "Provides documented federal training, qualification, logistics, or sustainment "
            "capacity for uncrewed-aircraft operators and systems."
        ),
    },
    "federal_counter_uas": {
        "categories": [
            "Federal and defense customer access",
            "Programs and initiatives",
            "Research and technical depth",
        ],
        "domains": ["Counter-UAS", "Unmanned aircraft systems"],
        "capabilities": [
            "Testing, evaluation, verification, and validation",
            "Operations, maintenance, and sustainment",
        ],
        "missions": ["Counter-UAS", "Force protection and installation security"],
        "relevance": (
            "Provides documented federal counter-UAS training, capability development, "
            "experimentation, or operational integration."
        ),
    },
    "aviation_site": {
        "categories": ["Physical infrastructure and logistics", "Manufacturing and supply chain"],
        "domains": ["Unmanned aircraft systems"],
        "capabilities": [
            "Manufacturing, materials, and prototyping",
            "Operations, maintenance, and sustainment",
        ],
        "missions": ["Training and experimentation", "Logistics and contested logistics"],
        "relevance": (
            "Provides documented aviation-accessible land, facilities, or development capacity "
            "relevant to uncrewed-aircraft research, production, training, and operations."
        ),
    },
}

ASSET_DETAIL_ENRICHMENT = {
    "MITRE National Range": {
        "activity_status": "active",
        "current_activity": (
            "MITRE operates the Orange County range for controlled testing, evaluation, and "
            "prototyping of UAS, counter-UAS, ground systems, communications, and related "
            "technologies."
        ),
        "partnership_opportunities": (
            "MITRE states that government, academic, and industry partners can discuss range "
            "use for prototyping, testing, training, demonstrations, and independent validation."
        ),
        "activity_source_url": SOURCES["mitre_range"][1],
        "activity_last_verified_at": CATALOG_DATE,
        "owner_operator": "MITRE",
        "development_status": "operational",
        "development_notes": (
            "The public fact sheet describes 16 acres of dedicated airspace, hundreds of acres "
            "of accessible land, and thousands of acres of aerial access; it does not describe "
            "that acreage as generally available development land."
        ),
        "infrastructure_access": (
            "Powered operations center, offices and work areas, storage, 5G connectivity, "
            "outdoor charging, internet, training space, and testing support."
        ),
        "development_source_url": SOURCES["mitre_range"][1],
        "development_last_verified_at": CATALOG_DATE,
    },
    "Virginia Economic Development Partnership": {
        "activity_status": "active",
        "current_activity": (
            "VEDP markets Virginia's unmanned-systems sector and provides companies with "
            "business intelligence, site-selection guidance, incentive support, and talent "
            "solutions."
        ),
        "partnership_opportunities": (
            "Domestic and international companies considering a Virginia location can use the "
            "industry-page contacts for confidential business-development assistance."
        ),
        "activity_source_url": VEDP_UXS,
        "activity_last_verified_at": CATALOG_DATE,
        "contact_text": "Unmanned-systems business attraction and site-selection inquiries",
        "contact_phone": "804-489-4391",
        "contact_email": "sburnette@vedp.org",
        "contact_url": VEDP_UXS,
    },
    "Hampton Roads Alliance": {
        "activity_status": "active",
        "current_activity": (
            "The Alliance provides regional business development, business intelligence, real "
            "estate solutions, and marketing; its technology assessment identifies autonomous "
            "systems as a Hampton Roads opportunity area."
        ),
        "partnership_opportunities": (
            "Companies considering a Hampton Roads expansion or relocation can contact the "
            "Alliance for regional economic-development and site support."
        ),
        "activity_source_url": SOURCES["hampton_roads_alliance"][1],
        "activity_last_verified_at": CATALOG_DATE,
        "contact_text": "Regional business attraction and economic-development inquiries",
        "contact_phone": "757-627-2315",
        "contact_email": "info@757alliance.com",
        "contact_url": "https://hamptonroadsalliance.com/",
    },
    "GO Virginia": {
        "activity_status": "active",
        "current_activity": (
            "GO Virginia supports collaborative economic-development projects through nine "
            "regional councils and publishes current projects and program performance resources."
        ),
        "partnership_opportunities": (
            "Potential project partners can review the current program manual and work through "
            "the applicable regional council on collaborative, traded-sector proposals."
        ),
        "activity_source_url": SOURCES["go_virginia"][1],
        "activity_last_verified_at": CATALOG_DATE,
        "contact_text": "GO Virginia program and regional-council information",
        "contact_phone": "804-371-7000",
        "contact_url": SOURCES["go_virginia"][1],
    },
    "Shenandoah Valley Aviation Technology Park": {
        "activity_status": "developing",
        "current_activity": (
            "Two 14,000-square-foot corporate hangars are complete, and publicly funded utility "
            "work supports later phases of the Aviation Technology Park."
        ),
        "partnership_opportunities": (
            "The airport describes the park as a site for aviation-related business growth; "
            "current space and project availability must be confirmed with the airport."
        ),
        "activity_source_url": SOURCES["shd_tech_park"][1],
        "activity_last_verified_at": CATALOG_DATE,
        "owner_operator": "Shenandoah Valley Regional Airport Commission",
        "available_acreage": 58,
        "development_status": "in-development",
        "development_notes": (
            "The 58-acre park has two completed hangars. Its master plan identifies capacity "
            "for up to five additional hangars; this figure is a published site total, not a "
            "claim that all acreage is currently available."
        ),
        "infrastructure_access": (
            "Road and taxiway access, parking, completed site work, and water and sewer utility "
            "relocation supporting future hangars."
        ),
        "development_source_url": SOURCES["shd_tech_park_site"][1],
        "development_last_verified_at": CATALOG_DATE,
    },
    "Stafford Regional Airport AAM Integration Project Site": {
        "activity_status": "pilot",
        "current_activity": (
            "Stafford Regional Airport is one of the three airport sites shown in the "
            "Stafford-Warrenton-Winchester project, which focuses on integrating drone "
            "operations into the National Airspace System."
        ),
        "partnership_opportunities": (
            "Program and participation questions can be directed to the Virginia Department of "
            "Aviation Advanced Air Mobility Program Manager."
        ),
        "activity_source_url": SOURCES["doav_aam"][1],
        "activity_last_verified_at": CATALOG_DATE,
        "contact_text": "Virginia Advanced Air Mobility Program Manager, Scott Denny",
        "contact_phone": "804-236-3638",
        "contact_email": "scott.denny@doav.virginia.gov",
        "contact_url": SOURCES["doav_aam"][1],
    },
    "Virginia Advanced Air Mobility Program": {
        "activity_status": "active",
        "current_activity": (
            "DOAV lists active work on multistate collaboration, smart airspace, electric "
            "aircraft demonstrations, the Stafford-Warrenton-Winchester project, statewide "
            "planning, community outreach, and airport integration."
        ),
        "partnership_opportunities": (
            "Statewide AAM program questions and stakeholder coordination are routed through "
            "the DOAV Advanced Air Mobility Program Manager."
        ),
        "activity_source_url": SOURCES["doav_aam"][1],
        "activity_last_verified_at": CATALOG_DATE,
        "contact_text": "Virginia Advanced Air Mobility Program Manager, Scott Denny",
        "contact_phone": "804-236-3638",
        "contact_email": "scott.denny@doav.virginia.gov",
        "contact_url": SOURCES["doav_aam"][1],
    },
    "Virginia Department of Aviation": {
        "activity_status": "active",
        "current_activity": (
            "DOAV leads statewide aviation programs and publishes current advanced-air-mobility "
            "goals, projects, resources, and airport-integration work."
        ),
        "partnership_opportunities": (
            "AAM program inquiries are routed through the department's named program manager; "
            "airport-development inquiries use the applicable agency program contact."
        ),
        "activity_source_url": SOURCES["doav_aam"][1],
        "activity_last_verified_at": CATALOG_DATE,
        "contact_text": "Virginia Department of Aviation public information",
        "contact_phone": "804-236-3624",
        "contact_url": SOURCES["doav_aam"][1],
    },
    "Virginia Flight Information Exchange": {
        "activity_status": "active",
        "current_activity": (
            "Virginia FIX provides an information-sharing capability for state and local "
            "governments and UAS stakeholders to address safety and policy concerns while "
            "supporting integrated airspace."
        ),
        "partnership_opportunities": (
            "The DOAV program page provides the public Virginia FIX site, concept-of-operations "
            "materials, and agency contact route."
        ),
        "activity_source_url": SOURCES["virginia_fix"][1],
        "activity_last_verified_at": CATALOG_DATE,
        "contact_text": "Virginia Department of Aviation program information",
        "contact_phone": "804-236-3624",
        "contact_url": SOURCES["virginia_fix"][1],
    },
}

PLACES = {
    "Accomac": (37.720, -75.665),
    "Abingdon": (36.710, -81.975),
    "Afton": (38.029, -78.835),
    "Amherst": (37.585, -79.052),
    "Arlington": (38.881, -77.091),
    "Ashland": (37.759, -77.480),
    "Blackstone": (37.080, -77.997),
    "Blacksburg": (37.229, -80.414),
    "Bowling Green": (38.050, -77.347),
    "Chatham": (36.826, -79.398),
    "Charlottesville": (38.035, -78.503),
    "Chesapeake": (36.768, -76.288),
    "Chester": (37.356, -77.442),
    "Chilhowie": (36.798, -81.683),
    "Chincoteague": (37.934, -75.378),
    "Christiansburg": (37.130, -80.409),
    "Chantilly": (38.875, -77.442),
    "Charles City": (37.342, -77.073),
    "Clifton Forge": (37.817, -79.824),
    "Colonial Heights": (37.244, -77.410),
    "Courtland": (36.716, -77.068),
    "Culpeper": (38.473, -77.996),
    "Danville": (36.586, -79.395),
    "Dahlgren": (38.333, -77.031),
    "Dulles": (38.955, -77.448),
    "Eastville": (37.352, -75.946),
    "Emory": (36.772, -81.831),
    "Farmville": (37.302, -78.391),
    "Fairfax": (38.846, -77.307),
    "Fredericksburg": (38.303, -77.461),
    "Front Royal": (38.918, -78.194),
    "Glen Allen": (37.666, -77.506),
    "Gloucester": (37.414, -76.526),
    "Grundy": (37.278, -82.100),
    "Hampton": (37.030, -76.346),
    "Hanover": (37.766, -77.370),
    "Harrisonburg": (38.449, -78.869),
    "Haymarket": (38.812, -77.636),
    "Henrico": (37.632, -77.515),
    "Hopewell": (37.305, -77.287),
    "King George": (38.269, -77.184),
    "Lynchburg": (37.414, -79.142),
    "Leesburg": (39.116, -77.564),
    "Lexington": (37.785, -79.442),
    "Lorton": (38.704, -77.228),
    "Manassas": (38.751, -77.475),
    "Madison": (38.380, -78.258),
    "Marion": (36.834, -81.514),
    "Martinsville": (36.691, -79.873),
    "Mattaponi": (37.529, -76.765),
    "Melfa": (37.649, -75.741),
    "Middletown": (39.027, -78.280),
    "New Market": (38.647, -78.671),
    "Newport News": (37.087, -76.473),
    "Norfolk": (36.851, -76.286),
    "Occoquan": (38.681, -77.260),
    "Orange": (38.245, -78.013),
    "Portsmouth": (36.836, -76.298),
    "Powhatan": (37.542, -77.919),
    "Petersburg": (37.227, -77.402),
    "Paeonian Springs": (39.149, -77.620),
    "Prince George": (37.221, -77.289),
    "South Prince George": (37.158, -77.387),
    "Quantico": (38.522, -77.290),
    "Radford": (37.132, -80.576),
    "Reston": (38.959, -77.357),
    "Richmond": (37.541, -77.436),
    "Roanoke": (37.271, -79.941),
    "Rocky Mount": (36.997, -79.892),
    "Rustburg": (37.276, -79.100),
    "Scottsville": (37.798, -78.495),
    "Springfield": (38.789, -77.187),
    "Stafford": (38.422, -77.408),
    "Sterling": (39.006, -77.428),
    "Staunton": (38.150, -79.072),
    "Sedley": (36.790, -76.590),
    "Suffolk": (36.728, -76.584),
    "Bedford": (37.334, -79.523),
    "Boydton": (36.667, -78.387),
    "Spotsylvania": (38.200, -77.589),
    "Virginia Beach": (36.853, -75.978),
    "Vienna": (38.883, -77.225),
    "Wallops Island": (37.940, -75.467),
    "Warm Springs": (38.052, -79.781),
    "Williamsburg": (37.271, -76.707),
    "Weyers Cave": (38.288, -78.913),
    "Wise": (36.975, -82.576),
    "Winchester": (39.185, -78.163),
    "Wytheville": (36.949, -81.084),
    "Yorktown": (37.239, -76.510),
}

# Specific locations are anchored to public addresses, campuses, terminal entrances,
# or installation administrative points. "Site" does not claim an operationally exact
# location within a large or access-controlled property.
LOCATION_OVERRIDES = {
    "Adaptive Aerospace Group": {
        "address_line": "22 Enterprise Parkway, Suite 320",
        "postal_code": "23666",
        "latitude": 37.056391,
        "longitude": -76.406700,
        "source": (
            "Adaptive Aerospace Group contact information",
            "https://adaptiveaero.com/",
        ),
    },
    "Virginia Department of Aviation": {
        "address_line": "5702 Gulfstream Road",
        "postal_code": "23250",
        "latitude": 37.512142,
        "longitude": -77.332758,
        "location_precision": "exact",
        "source": (
            "Virginia Department of Aviation Advanced Air Mobility",
            SOURCES["doav_aam"][1],
        ),
    },
    "Virginia Advanced Air Mobility Program": {
        "address_line": "5702 Gulfstream Road",
        "postal_code": "23250",
        "latitude": 37.512142,
        "longitude": -77.332758,
        "location_precision": "site",
        "source": (
            "Virginia Department of Aviation Advanced Air Mobility",
            SOURCES["doav_aam"][1],
        ),
    },
    "Virginia Flight Information Exchange": {
        "address_line": "",
        "city": "",
        "postal_code": "",
        "latitude": None,
        "longitude": None,
        "location_precision": "regional",
        "source": (
            "Virginia Department of Aviation Flight Information Exchange",
            SOURCES["virginia_fix"][1],
        ),
    },
    "Advanced Aircraft Company": {
        "address_line": "1100 Exploration Way",
        "postal_code": "23666",
        "latitude": 37.082521,
        "longitude": -76.399763,
        "source": (
            "Advanced Aircraft Company contact information",
            "https://advancedaircraftcompany.com/contact/",
        ),
    },
    "Agricision": {
        "address_line": "13199 Wakefield Road",
        "postal_code": "23878",
        "latitude": 36.841546,
        "longitude": -77.057713,
        "source": ("Agricision contact information", "https://www.agricisioninc.com/contact"),
    },
    "AUVSI Hampton Roads Chapter": {
        "city": "",
        "latitude": None,
        "longitude": None,
        "location_precision": "regional",
    },
    "James City County Police Drone as First Responder Program": {
        "address_line": "4600 Opportunity Way",
        "postal_code": "23188",
        "latitude": 37.337991,
        "longitude": -76.757712,
        "source": (
            "James City County DFR test-flight location",
            "https://www.jamescitycountyva.gov/m/newsflash/Home/Detail/6334",
        ),
    },
    "Christopher Newport University": {
        "address_line": "1 Avenue of the Arts",
        "postal_code": "23606",
        "latitude": 37.059929,
        "longitude": -76.488306,
        "source": (
            "Christopher Newport University contact information",
            "https://cnu.edu/whoweare/contactus/",
        ),
    },
    "City of Virginia Beach UAS Program": {
        "address_line": "2401 Courthouse Drive",
        "postal_code": "23456",
        "latitude": 36.750163,
        "longitude": -76.054885,
        "source": ("City of Virginia Beach", "https://virginiabeach.gov/"),
    },
    "CNU Autonomous Systems and Drone Lab": {
        "address_line": "1 Avenue of the Arts",
        "postal_code": "23606",
        "latitude": 37.059929,
        "longitude": -76.488306,
        "source": (
            "CNU Science and Engineering Research Center drone lab",
            "https://cnu.edu/news/2026/02/19-cnu-serc-drone-lab/",
        ),
    },
    "CNU Capable Humanitarian Robotics and Intelligent Systems Lab": {
        "address_line": "1 Avenue of the Arts",
        "postal_code": "23606",
        "latitude": 37.059929,
        "longitude": -76.488306,
        "source": (
            "Christopher Newport University contact information",
            "https://cnu.edu/whoweare/contactus/",
        ),
    },
    "Coast Guard Atlantic Area and Fifth Coast Guard District": {
        "address_line": "431 Crawford Street",
        "postal_code": "23704",
        "latitude": 36.836893,
        "longitude": -76.297851,
        "source": ("U.S. Coast Guard Fifth District", "https://www.uscg.mil/Our-Organization/D5/"),
    },
    "Craney Island Marine Terminal Project": {
        "address_line": "Craney Island",
        "postal_code": "23703",
        "latitude": 36.892370,
        "longitude": -76.359388,
        "source": (
            "Craney Island Eastward Expansion project",
            "https://www.nao.usace.army.mil/Missions/Civil-Works/Craney-Island/",
        ),
    },
    "Dam Neck Annex": {
        "address_line": "1912 Regulus Avenue",
        "postal_code": "23461",
        "latitude": 36.776959,
        "longitude": -75.957393,
        "source": (
            "Naval Air Station Oceana and Dam Neck Annex installation guide",
            "https://cnrma.cnic.navy.mil/Installations/NAS-Oceana/",
        ),
    },
    "DroneUp": {
        "address_line": "160 Newtown Road, Suite 302",
        "postal_code": "23462",
        "latitude": 36.842642,
        "longitude": -76.186071,
        "source": (
            "DroneUp privacy policy and contact information",
            "https://www.droneup.com/privacy-policy",
        ),
    },
    "Fort Eustis - Joint Base Langley-Eustis": {
        "address_line": "705 Washington Boulevard",
        "postal_code": "23604",
        "latitude": 37.161782,
        "longitude": -76.577685,
        "source": (
            "Joint Base Langley-Eustis contact information",
            "https://www.jble.af.mil/Home/Contact/",
        ),
    },
    "HII Unmanned Systems Center of Excellence": {
        "address_line": "North Campus Parkway at Commander Shepard Boulevard",
        "postal_code": "23666",
        "latitude": 37.074905,
        "longitude": -76.402317,
        "source": (
            "City of Hampton: HII Unmanned Systems Center site",
            "https://www.hampton.gov/CivicAlerts.aspx?AID=4656&ARC=9365",
        ),
    },
    "HUSH Aerospace": {
        "address_line": "2873 Crusader Circle",
        "postal_code": "23453",
        "latitude": 36.800894,
        "longitude": -76.066090,
        "source": ("HUSH Aerospace contact information", "https://www.hush.aero/contact-hush"),
    },
    "Joint Expeditionary Base Little Creek-Fort Story": {
        "address_line": "1815 Seabee Road",
        "postal_code": "23459",
        "latitude": 36.918239,
        "longitude": -76.156529,
        "source": (
            "Joint Expeditionary Base Little Creek-Fort Story contact information",
            "https://cnrma.cnic.navy.mil/Installations/JEB-Little-Creek-Fort-Story/Contact-Us/",
        ),
    },
    "Langley Air Force Base - Joint Base Langley-Eustis": {
        "address_line": "230 East Flight Line Road",
        "postal_code": "23665",
        "latitude": 37.079979,
        "longitude": -76.351484,
        "source": (
            "Joint Base Langley-Eustis contact information",
            "https://www.jble.af.mil/Home/Contact/",
        ),
    },
    "Longbow Unmanned Systems Research and Test Center": {
        "address_line": "96 Stilwell Road",
        "postal_code": "23651",
        "latitude": 37.010449,
        "longitude": -76.312444,
        "source": (
            "Unmanned Systems Research and Technology Center",
            "https://www.usrtc.org/about-us",
        ),
    },
    "NASA Langley Autonomy Incubator": {
        "address_line": "2 Langley Boulevard",
        "postal_code": "23681",
        "latitude": 37.085639,
        "longitude": -76.380667,
        "source": (
            "NASA Langley maps and directions",
            "https://www.nasa.gov/centers-and-facilities/langley/maps-directions/",
        ),
    },
    "NASA Langley CERTAIN": {
        "address_line": "2 Langley Boulevard",
        "postal_code": "23681",
        "latitude": 37.085639,
        "longitude": -76.380667,
        "source": (
            "NASA Langley maps and directions",
            "https://www.nasa.gov/centers-and-facilities/langley/maps-directions/",
        ),
    },
    "NASA Langley Research Center": {
        "address_line": "2 Langley Boulevard",
        "postal_code": "23681",
        "latitude": 37.085639,
        "longitude": -76.380667,
        "source": (
            "NASA Langley maps and directions",
            "https://www.nasa.gov/centers-and-facilities/langley/maps-directions/",
        ),
    },
    "National Institute of Aerospace": {
        "address_line": "1100 Exploration Way",
        "postal_code": "23666",
        "latitude": 37.082521,
        "longitude": -76.399763,
        "source": (
            "National Institute of Aerospace contact information",
            "https://www.nianet.org/contact/",
        ),
    },
    "Naval Air Station Oceana": {
        "address_line": "1750 Tomcat Boulevard",
        "postal_code": "23460",
        "latitude": 36.814477,
        "longitude": -76.029021,
        "source": (
            "Naval Air Station Oceana contact information",
            "https://cnrma.cnic.navy.mil/Installations/NAS-Oceana/Contact-Us/",
        ),
    },
    "Naval Medical Center Portsmouth": {
        "address_line": "620 John Paul Jones Circle",
        "postal_code": "23708",
        "latitude": 36.843389,
        "longitude": -76.305001,
        "source": (
            "Naval Medical Center Portsmouth directory",
            "https://portsmouth.tricare.mil/About-Us/Phone-Directory",
        ),
    },
    "Naval Station Norfolk": {
        "address_line": "1530 Gilbert Street",
        "postal_code": "23511",
        "latitude": 36.948171,
        "longitude": -76.302661,
        "source": (
            "Naval Station Norfolk contact information",
            "https://cnrma.cnic.navy.mil/Installations/NAVSTA-Norfolk/Contact-Us/",
        ),
    },
    "Naval Support Activity Hampton Roads": {
        "address_line": "7918 Blandy Road",
        "postal_code": "23511",
        "latitude": 36.922618,
        "longitude": -76.302013,
        "source": (
            "Naval Support Activity Hampton Roads contact information",
            "https://cnrma.cnic.navy.mil/About/Contact-Us/",
        ),
    },
    "Naval Support Activity Northwest Annex": {
        "address_line": "1320 Northwest Boulevard",
        "city": "Chesapeake",
        "postal_code": "23322",
        "latitude": 36.566582,
        "longitude": -76.247058,
        "source": (
            "Naval Support Activity Hampton Roads Northwest Annex",
            "https://cnrma.cnic.navy.mil/Installations/NSA-Hampton-Roads/",
        ),
    },
    "Naval Weapons Station Yorktown": {
        "address_line": "160 Main Road",
        "postal_code": "23691",
        "latitude": 37.232649,
        "longitude": -76.548122,
        "source": (
            "Naval Weapons Station Yorktown contact information",
            "https://cnrma.cnic.navy.mil/Installations/WPNSTA-Yorktown/Contact-Us/",
        ),
    },
    "Newport News Marine Terminal": {
        "address_line": "25th Street at Warwick Boulevard",
        "postal_code": "23607",
        "latitude": 36.985800,
        "longitude": -76.434700,
        "source": (
            "Port of Virginia terminal directions",
            "https://operations.portofvirginia.com/terminal-directions/",
        ),
    },
    "Newport News Shipbuilding": {
        "address_line": "4101 Washington Avenue",
        "postal_code": "23607",
        "latitude": 36.986329,
        "longitude": -76.435738,
        "source": ("HII company locations", "https://www.hii.com/company-overview"),
    },
    "Norfolk District, U.S. Army Corps of Engineers": {
        "address_line": "803 Front Street",
        "postal_code": "23510",
        "latitude": 36.855907,
        "longitude": -76.304776,
        "source": (
            "U.S. Army Corps of Engineers Norfolk District",
            "https://www.nao.usace.army.mil/",
        ),
    },
    "Norfolk International Terminals": {
        "address_line": "7737 Hampton Boulevard",
        "postal_code": "23505",
        "latitude": 36.915927,
        "longitude": -76.308572,
        "source": (
            "Port of Virginia terminal directions",
            "https://operations.portofvirginia.com/terminal-directions/",
        ),
    },
    "Norfolk Naval Shipyard": {
        "address_line": "1 Maple Avenue",
        "postal_code": "23709",
        "latitude": 36.819272,
        "longitude": -76.297312,
        "source": ("Norfolk Naval Shipyard", "https://www.navsea.navy.mil/Home/Shipyards/Norfolk/"),
    },
    "ODU Unmanned and Autonomous Vehicle Laboratory": {
        "address_line": "5115 Hampton Boulevard",
        "postal_code": "23529",
        "latitude": 36.889280,
        "longitude": -76.303179,
        "source": (
            "Old Dominion University contact information",
            "https://www.odu.edu/about/contact",
        ),
    },
    "Old Dominion University": {
        "address_line": "5115 Hampton Boulevard",
        "postal_code": "23529",
        "latitude": 36.889280,
        "longitude": -76.303179,
        "source": (
            "Old Dominion University contact information",
            "https://www.odu.edu/about/contact",
        ),
    },
    "Old Dominion University UAS Operations Program": {
        "address_line": "5115 Hampton Boulevard",
        "postal_code": "23529",
        "latitude": 36.889280,
        "longitude": -76.303179,
        "source": (
            "Old Dominion University contact information",
            "https://www.odu.edu/about/contact",
        ),
    },
    "Portsmouth Marine Terminal": {
        "address_line": "2000 Seaboard Avenue",
        "postal_code": "23707",
        "latitude": 36.854497,
        "longitude": -76.324844,
        "source": (
            "Port of Virginia terminal directions",
            "https://operations.portofvirginia.com/terminal-directions/",
        ),
    },
    "The Port of Virginia": {
        "address_line": "101 West Main Street, Suite 600",
        "postal_code": "23510",
        "latitude": 36.846140,
        "longitude": -76.293320,
        "source": (
            "Port of Virginia contact information",
            "https://www.portofvirginia.com/contact/",
        ),
    },
    "Tidewater Community College Unmanned Systems Courses": {
        "address_line": "1428 Cedar Road",
        "postal_code": "23322",
        "latitude": 36.724948,
        "longitude": -76.295519,
        "source": (
            "Tidewater Community College Chesapeake Campus",
            "https://www.tcc.edu/come-to-tcc/chesapeake-campus/",
        ),
    },
    "U.S. Coast Guard Base Portsmouth": {
        "address_line": "4000 Coast Guard Boulevard",
        "postal_code": "23703",
        "latitude": 36.873685,
        "longitude": -76.377469,
        "source": (
            "U.S. Coast Guard Sector Virginia",
            "https://www.atlanticarea.uscg.mil/Our-Organization/District-Units/East-District/Sector-Virginia/",
        ),
    },
    "Virginia Institute for Spaceflight and Autonomy": {
        "address_line": "4111 Monarch Way",
        "postal_code": "23508",
        "latitude": 36.882436,
        "longitude": -76.300479,
        "source": (
            "ODU Enterprise Research and Innovation",
            "https://www.odu.edu/research/enterprise-research-and-innovation",
        ),
    },
    "Virginia Institute of Marine Science": {
        "address_line": "1375 Greate Road",
        "city": "Gloucester Point",
        "postal_code": "23062",
        "latitude": 37.249323,
        "longitude": -76.500000,
        "source": (
            "Virginia Institute of Marine Science street addresses",
            "https://www.vims.edu/intranet/street_addresses/",
        ),
    },
    "Virginia International Gateway": {
        "address_line": "1000 Virginia International Gateway Boulevard",
        "postal_code": "23703",
        "latitude": 36.872573,
        "longitude": -76.358894,
        "source": (
            "Port of Virginia terminal directions",
            "https://operations.portofvirginia.com/terminal-directions/",
        ),
    },
    "Virginia Modeling, Analysis and Simulation Center": {
        "address_line": "1030 University Boulevard",
        "postal_code": "23435",
        "latitude": 36.869656,
        "longitude": -76.418307,
        "source": (
            "Old Dominion University VMASC location",
            "https://www.odu.edu/sites/default/files/documents/nutrient-management-plan.pdf",
        ),
    },
    "Virginia Peninsula Community College Drone Flight Technician Certificate": {
        "address_line": "99 Thomas Nelson Drive",
        "postal_code": "23666",
        "latitude": 37.064091,
        "longitude": -76.424002,
        "source": (
            "Virginia Peninsula Community College Hampton Campus",
            "https://www.vpcc.edu/about/locations/hampton-campus/",
        ),
    },
    "Virginia Space Grant Consortium Drone Academies": {
        "address_line": "600 Butler Farm Road",
        "postal_code": "23666",
        "latitude": 37.062071,
        "longitude": -76.414915,
        "source": (
            "NASA Virginia Space Grant Consortium directory",
            "https://www.nasa.gov/learning-resources/national-space-grant-college-and-fellowship-project/consortium-directors/",
        ),
    },
    "William & Mary": {
        "address_line": "116 Jamestown Road",
        "postal_code": "23185",
        "latitude": 37.270259,
        "longitude": -76.708061,
        "source": (
            "William & Mary contact information",
            "https://www.wm.edu/admission/undergraduateadmission/contactus/",
        ),
    },
    "Hampton University": {
        "address_line": "100 East Queen Street",
        "postal_code": "23668",
        "latitude": 37.023632,
        "longitude": -76.338129,
        "source": (
            "Hampton University contact information",
            "https://home.hamptonu.edu/about/contact-hu/",
        ),
    },
    "Hampton University Uncrewed Aircraft Systems Program": {
        "address_line": "100 East Queen Street",
        "postal_code": "23668",
        "latitude": 37.023632,
        "longitude": -76.338129,
        "source": (
            "Hampton University contact information",
            "https://home.hamptonu.edu/about/contact-hu/",
        ),
    },
    "Norfolk State University": {
        "address_line": "700 Park Avenue",
        "postal_code": "23504",
        "latitude": 36.849182,
        "longitude": -76.267977,
        "source": ("Norfolk State University", "https://www.nsu.edu/About"),
    },
    "Virginia Military Institute": {
        "address_line": "319 Letcher Avenue",
        "postal_code": "24450",
        "latitude": 37.789600,
        "longitude": -79.437067,
        "source": (
            "Virginia Military Institute map and directions",
            "https://www.vmi.edu/about/our-location/map-and-directions/",
        ),
    },
    "Norfolk State Tactical Autonomy Research Program": {
        "address_line": "700 Park Avenue",
        "postal_code": "23504",
        "latitude": 36.849182,
        "longitude": -76.267977,
        "source": ("Norfolk State University", "https://www.nsu.edu/About"),
    },
    "Norfolk State Drone Photography Course": {
        "address_line": "700 Park Avenue",
        "postal_code": "23504",
        "latitude": 36.849182,
        "longitude": -76.267977,
        "source": ("Norfolk State University", "https://www.nsu.edu/About"),
    },
    "Fulcrum Concepts": {
        "address_line": "1776 Patriot Way",
        "postal_code": "23110",
        "latitude": 37.523935,
        "longitude": -76.756529,
        "source": (
            "Fulcrum Concepts contact information",
            "https://fulcrumconceptsllc.com/contact/",
        ),
    },
    "ICI Services": {
        "address_line": "500 Viking Drive, Suite 400",
        "postal_code": "23452",
        "latitude": 36.829671,
        "longitude": -76.067127,
        "source": ("ICI Services", "https://www.icisrvcs.com/"),
    },
    "Norfolk Police UAS Team": {
        "address_line": "100 Brooke Avenue",
        "postal_code": "23510",
        "latitude": 36.848642,
        "longitude": -76.291219,
        "source": (
            "Norfolk Police contact information",
            "https://www.norfolk.gov/5729/About-Us",
        ),
    },
    "Norfolk Harbor Patrol Drone Capability": {
        "address_line": "100 Brooke Avenue",
        "postal_code": "23510",
        "latitude": 36.848642,
        "longitude": -76.291219,
        "source": (
            "Norfolk Harbor Patrol Unit",
            "https://www.norfolk.gov/6644/Harbor-Patrol-Unit",
        ),
    },
    "York County ROVER Team": {
        "address_line": "224 Ballard Street",
        "postal_code": "23690",
        "latitude": 37.235331,
        "longitude": -76.509799,
        "source": (
            "York County contact information",
            "https://www.yorkcounty.gov/1874/The-ROVER-Team",
        ),
    },
    "Newport News Police and Fire Drone Unit": {
        "address_line": "9710 Jefferson Avenue",
        "postal_code": "23605",
        "latitude": 37.029425,
        "longitude": -76.450613,
        "source": ("Newport News Drone Unit", "https://www.nnva.gov/2394/Drone-Unit"),
    },
    "Suffolk Police UAS Unit": {
        "address_line": "111 Henley Place",
        "postal_code": "23434",
        "latitude": 36.730070,
        "longitude": -76.590253,
        "source": (
            "Suffolk Police Department directory",
            "https://www.suffolkva.us/Directory.aspx?did=28",
        ),
    },
    "NSWC Carderock Combatant Craft Division": {
        "address_line": "1815 Seabee Road",
        "city": "Virginia Beach",
        "postal_code": "23459",
        "latitude": 36.918239,
        "longitude": -76.156529,
        "source": (
            "Joint Expeditionary Base Little Creek-Fort Story contact information",
            "https://cnrma.cnic.navy.mil/Installations/JEB-Little-Creek-Fort-Story/Contact-Us/",
        ),
    },
    "Harrowgate Drone Park": {
        "address_line": "15501 Harrowgate Road",
        "city": "Chester",
        "postal_code": "23831",
        "latitude": 37.306145,
        "longitude": -77.427338,
        "source": (
            "Chesterfield County Drone Park dedication",
            "https://www.chesterfield.gov/Calendar.aspx?EID=4094",
        ),
    },
    "Blue Vigil": {
        "address_line": "45449 Severn Way, Suite 169",
        "postal_code": "20166",
        "latitude": 39.020680,
        "longitude": -77.426677,
        "source": ("Blue Vigil contact information", "https://www.bluevigil.com/"),
    },
    "P1 Technologies Keltech Division": {
        "address_line": "6591 Merriman Road",
        "postal_code": "24018",
        "latitude": 37.197351,
        "longitude": -79.999510,
        "source": (
            "P1 Technologies contact information",
            "https://www.p1tec.com/contact-us",
        ),
    },
    "Virginia Smart Community Testbed": {
        "address_line": "2143 Richmond Highway",
        "postal_code": "22554",
        "latitude": 38.423823,
        "longitude": -77.408604,
        "source": ("Virginia Smart Community Testbed", "https://vatestbed.com/"),
    },
    "Virginia Spaceport Authority": {
        "address_line": "101 West Main Street, Suite 602",
        "city": "Norfolk",
        "postal_code": "23510",
        "latitude": 36.846140,
        "longitude": -76.293320,
        "source": (
            "Virginia Spaceport Authority contact information",
            "https://www.vaspace.org/contact-us",
        ),
    },
    "ODU Institute for Autonomous and Connected Systems": {
        "address_line": "5115 Hampton Boulevard",
        "postal_code": "23529",
        "latitude": 36.889280,
        "longitude": -76.303179,
        "source": ("Old Dominion University contact information", "https://www.odu.edu/about/contact"),
    },
    "ODU Uncrewed Systems Design and Development Minor": {
        "address_line": "5115 Hampton Boulevard",
        "postal_code": "23529",
        "latitude": 36.889280,
        "longitude": -76.303179,
        "source": ("Old Dominion University contact information", "https://www.odu.edu/about/contact"),
    },
    "ODU Drone Certificate Program": {
        "address_line": "5115 Hampton Boulevard",
        "postal_code": "23529",
        "latitude": 36.889280,
        "longitude": -76.303179,
        "source": ("Old Dominion University contact information", "https://www.odu.edu/about/contact"),
    },
    "ODU Maritime Autonomous Systems Test Site": {
        "address_line": "1311 Bayville Street",
        "postal_code": "23503",
        "latitude": 36.964814,
        "longitude": -76.288880,
        "source": (
            "City of Norfolk Willoughby Boat Ramp",
            "https://www.norfolk.gov/Facilities/Facility/Details/Willoughby-Boat-Ramp-211",
        ),
    },
    "VIMS Collaboratory for Physical Oceanography": {
        "address_line": "1375 Greate Road",
        "city": "Gloucester Point",
        "postal_code": "23062",
        "latitude": 37.249323,
        "longitude": -76.500000,
        "source": (
            "Virginia Institute of Marine Science street addresses",
            "https://www.vims.edu/intranet/street_addresses/",
        ),
    },
    "VIMS Autonomous Systems Laboratory": {
        "address_line": "1375 Greate Road",
        "city": "Gloucester Point",
        "postal_code": "23062",
        "latitude": 37.249323,
        "longitude": -76.500000,
        "source": (
            "Virginia Institute of Marine Science street addresses",
            "https://www.vims.edu/intranet/street_addresses/",
        ),
    },
    "VIMS Harmful Algal Bloom Drone Monitoring": {
        "address_line": "1375 Greate Road",
        "city": "Gloucester Point",
        "postal_code": "23062",
        "latitude": 37.249323,
        "longitude": -76.500000,
        "source": (
            "Virginia Institute of Marine Science street addresses",
            "https://www.vims.edu/intranet/street_addresses/",
        ),
    },
    "Caroline County Fire and Rescue UAS Program": {
        "address_line": "233 West Broaddus Avenue",
        "postal_code": "22427",
        "latitude": 38.049079,
        "longitude": -77.356210,
        "source": (
            "Caroline County Fire and Rescue contact information",
            "https://www.co.caroline.va.us/230/Fire-Rescue",
        ),
    },
    "Gloucester County Sheriff's Office UAS Program": {
        "address_line": "7502 Justice Drive",
        "postal_code": "23061",
        "latitude": 37.417783,
        "longitude": -76.528513,
        "source": ("Gloucester County Sheriff's Office", "https://gloucesterva.gov/sheriff"),
    },
    "Hampton Joint Police and Fire UAS Unit": {
        "address_line": "22 Lincoln Street",
        "postal_code": "23669",
        "latitude": 37.028113,
        "longitude": -76.343479,
        "source": ("Hampton Division of Fire and Rescue", "https://www.hampton.gov/244/Fire-Rescue"),
    },
    "Chesapeake Police UAS Team": {
        "address_line": "304 Albemarle Drive",
        "postal_code": "23322",
        "latitude": 36.717383,
        "longitude": -76.247114,
        "source": ("Chesapeake Police Department", "https://www.cityofchesapeake.net/727/Police-Department"),
    },
    "Newport News Drones as First Responders Program": {
        "address_line": "9710 Jefferson Avenue",
        "postal_code": "23605",
        "latitude": 37.029425,
        "longitude": -76.450613,
        "source": ("Newport News Drone Unit", "https://www.nnva.gov/2394/Drone-Unit"),
    },
    "Colonial Heights Police Drone Program": {
        "address_line": "100 Highland Avenue",
        "postal_code": "23834",
        "latitude": 37.253604,
        "longitude": -77.410993,
        "source": (
            "Colonial Heights Police Department",
            "https://www.colonialheightsva.gov/156/Police",
        ),
    },
    "Hopewell Fire and EMS Drone Program": {
        "address_line": "200 South Hopewell Street",
        "postal_code": "23860",
        "latitude": 37.304522,
        "longitude": -77.283966,
        "source": ("Hopewell Fire and EMS", "https://hopewellva.gov/192/Fire-EMS"),
    },
    "Stafford County Sheriff's Office UAS Team": {
        "address_line": "1225 Courthouse Road",
        "postal_code": "22554",
        "latitude": 38.421101,
        "longitude": -77.413045,
        "source": (
            "Stafford County Sheriff's Office",
            "https://www.staffordsheriff.com/content/about/fieldoperations.cfm",
        ),
    },
    "Frederick County Sheriff's Office sUAS Program": {
        "address_line": "107 North Kent Street",
        "postal_code": "22601",
        "latitude": 39.184242,
        "longitude": -78.162454,
        "source": (
            "Frederick County Sheriff's Office Special Operations",
            "https://www.fcva.us/departments/sheriff-s-office/divisions/special-operations",
        ),
    },
    "NASA Langley ROAM UAS Operations Center": {
        "address_line": "Building Complex 1268, 2 Langley Boulevard",
        "postal_code": "23681",
        "latitude": 37.085639,
        "longitude": -76.380667,
        "source": (
            "NASA Langley maps and directions",
            "https://www.nasa.gov/centers-and-facilities/langley/maps-directions/",
        ),
    },
    "NASA Langley UAS Test Range": {
        "address_line": "NASA Langley Research Center, 2 Langley Boulevard",
        "postal_code": "23681",
        "latitude": 37.085639,
        "longitude": -76.380667,
        "source": (
            "NASA Langley maps and directions",
            "https://www.nasa.gov/centers-and-facilities/langley/maps-directions/",
        ),
    },
    "Wallops Research Park": {
        "address_line": "Aerospace Gateway at Mill Dam Road",
        "postal_code": "23337",
        "latitude": 37.934186,
        "longitude": -75.484632,
        "source": (
            "Accomack County Wallops Research Park",
            "https://www.accomack.gov/614/Background-Timeline",
        ),
    },
    "NSWC Dahlgren UAV Test Runway": {
        "address_line": "Runway 16/34, Naval Support Facility Dahlgren",
        "postal_code": "22448",
        "latitude": 38.333027,
        "longitude": -77.037130,
        "source": (
            "OpenStreetMap named-site map data",
            "https://www.openstreetmap.org/copyright",
        ),
    },
    "NSWCDD Dam Neck Activity": {
        "address_line": "1922 Regulus Avenue",
        "postal_code": "23461",
        "latitude": 36.776826,
        "longitude": -75.957372,
        "source": (
            "NSWCDD Dam Neck Activity visitor information",
            "https://www.navsea.navy.mil/Home/Warfare-Centers/NSWC-Dahlgren/Dam-Neck/",
        ),
    },
    "Navy TALSA East Small UAS Training Facility": {
        "address_line": "Joint Expeditionary Base Little Creek-Fort Story, 1815 Seabee Road",
        "postal_code": "23459",
        "latitude": 36.918239,
        "longitude": -76.156529,
        "source": (
            "Joint Expeditionary Base Little Creek-Fort Story contact information",
            "https://cnrma.cnic.navy.mil/Installations/JEB-Little-Creek-Fort-Story/Contact-Us/",
        ),
    },
    "Marine Corps Counter-Drone Team": {
        "address_line": "Weapons Training Battalion, 27211 Garand Road",
        "postal_code": "22134",
        "latitude": 38.531927,
        "longitude": -77.431232,
        "source": (
            "Weapons Training Battalion contact information",
            "https://www.trngcmd.marines.mil/Units/Weapons-Training-Battalion/Contact-Us/",
        ),
    },
    "Fairfax County Police Drone as First Responder Program": {
        "address_line": "12099 Government Center Parkway",
        "postal_code": "22035",
        "latitude": 38.857284,
        "longitude": -77.360811,
        "source": (
            "Fairfax County Police headquarters",
            "https://www.fairfaxcounty.gov/police/",
        ),
    },
    "Charles City County Sheriff's Office Drone Operations Team": {
        "address_line": "10780 Courthouse Road",
        "postal_code": "23030",
        "latitude": 37.341750,
        "longitude": -77.072764,
        "source": (
            "Charles City County Sheriff's Office directory",
            "https://www.charlescityva.us/directory.aspx?did=20",
        ),
    },
    "Bedford Fire Department UAS Program": {
        "address_line": "315 Bedford Avenue",
        "postal_code": "24523",
        "latitude": 37.336652,
        "longitude": -79.523684,
        "source": (
            "Bedford Fire Department contact information",
            "https://www.bedfordva.gov/154/Fire-Department",
        ),
    },
    "Radford University First Responder UAS Capability": {
        "address_line": "801 East Main Street",
        "postal_code": "24142",
        "latitude": 37.138524,
        "longitude": -80.547221,
        "source": (
            "Radford University contact information",
            "https://www.radford.edu/admissions/contact/index.html",
        ),
    },
    "MAG Aerospace": {
        "address_line": "12730 Fair Lakes Circle, Suite 600",
        "postal_code": "22033",
        "latitude": 38.858248,
        "longitude": -77.385442,
        "location_precision": "exact",
        "source": ("MAG Aerospace contact information", "https://www.magaero.com/connect/"),
    },
    "Inertial Labs": {
        "address_line": "39959 Catoctin Ridge Street",
        "postal_code": "20129",
        "latitude": 39.148926,
        "longitude": -77.620274,
        "location_precision": "exact",
        "source": (
            "Inertial Labs headquarters and R&D address",
            "https://inertiallabs.com/inertial-labs-inc/",
        ),
    },
    "DZYNE Technologies": {
        "address_line": "8280 Willow Oaks Corporate Drive, Suite 200",
        "postal_code": "22031",
        "latitude": 38.863831,
        "longitude": -77.230173,
        "location_precision": "exact",
        "source": (
            "U.S. SBIR portfolio company address",
            "https://www.sbir.gov/portfolio/406214",
        ),
    },
    "ENSCO": {
        "address_line": "2600 Park Tower Drive, Suite 400",
        "postal_code": "22180",
        "latitude": 38.882696,
        "longitude": -77.225255,
        "location_precision": "exact",
        "source": ("ENSCO locations", "https://www.ensco.com/contact/locations"),
    },
    "Scout Space": {
        "address_line": "2002 Edmund Halley Drive",
        "postal_code": "20191",
        "latitude": 38.951004,
        "longitude": -77.361571,
        "location_precision": "exact",
        "source": (
            "U.S. SBIR portfolio company address",
            "https://www.sbir.gov/portfolio/1543541",
        ),
    },
    "Universal Solutions International": {
        "address_line": "11827 Canon Boulevard, Suite 203",
        "postal_code": "23606",
        "latitude": 37.088151,
        "longitude": -76.470619,
        "location_precision": "exact",
        "source": ("Universal Solutions International", "https://usi-inc.com/"),
    },
    "Leidos": {
        "address_line": "1750 Presidents Street",
        "postal_code": "20190",
        "latitude": 38.958937,
        "longitude": -77.355528,
        "location_precision": "exact",
        "source": (
            "Leidos corporate headquarters",
            "https://investors.leidos.com/stockholder-resources/investor-faqs",
        ),
    },
    "CACI International": {
        "address_line": "12021 Sunset Hills Road",
        "postal_code": "20190",
        "latitude": 38.955088,
        "longitude": -77.357265,
        "location_precision": "exact",
        "source": (
            "CACI maritime and counter-UAS capability statement",
            "https://www.caci.com/sites/default/files/2022-11/F614_2210_Maritime_cUAS.pdf",
        ),
    },
    "Parsons": {
        "address_line": "14291 Park Meadow Drive, Suite 100",
        "postal_code": "20151",
        "latitude": 38.875067,
        "longitude": -77.441846,
        "location_precision": "exact",
        "source": ("Parsons office locations", "https://www.parsons.com/contact-us/"),
    },
    "Eagle Aviation Technologies": {
        "address_line": "7505 Warwick Boulevard",
        "postal_code": "23607",
        "latitude": 37.014492,
        "longitude": -76.448543,
        "location_precision": "exact",
        "source": (
            "Eagle Aviation Technologies contact information",
            "https://eagleaviationtech.com/contact-us",
        ),
    },
    "Virginia Economic Development Partnership": {
        "address_line": "901 East Cary Street",
        "postal_code": "23219",
        "latitude": 37.537283,
        "longitude": -77.437109,
        "location_precision": "exact",
        "source": (
            "Virginia Economic Development Partnership contact information",
            "https://www.vedp.org/contact-us",
        ),
    },
    "Hampton Roads Alliance": {
        "address_line": "3 Commercial Place, Suite 1320",
        "postal_code": "23510",
        "latitude": 36.845260,
        "longitude": -76.288798,
        "location_precision": "site",
        "source": (
            "Hampton Roads Alliance board meeting information",
            "https://hamptonroadsalliance.com/wp-content/uploads/2025/01/"
            "Minutes_Board-Meeting_April-19-2024.pdf",
        ),
    },
    "GO Virginia": {
        "address_line": "600 East Main Street, Suite 300",
        "postal_code": "23219",
        "latitude": 37.539841,
        "longitude": -77.438898,
        "location_precision": "exact",
        "source": ("GO Virginia", "https://www.dhcd.virginia.gov/gova"),
    },
    "Shenandoah Valley Aviation Technology Park": {
        "address_line": "77 Aviation Circle",
        "postal_code": "24486",
        "latitude": 38.263841,
        "longitude": -78.896447,
        "location_precision": "site",
        "source": (
            "Shenandoah Valley Aviation Technology Park site development",
            SOURCES["shd_tech_park_site"][1],
        ),
    },
    "Stafford Regional Airport AAM Integration Project Site": {
        "address_line": "95 Aviation Way",
        "postal_code": "22406",
        "latitude": 38.399142,
        "longitude": -77.456610,
        "location_precision": "site",
        "source": (
            "Virginia Airport Sponsor and Manager Directory",
            DOAV_SPONSOR_DIRECTORY,
        ),
    },
    "Newport News AirCommerce Park": {
        "address_line": "Newport News-Williamsburg International Airport, 900 Bland Boulevard",
        "postal_code": "23602",
        "latitude": 37.132177,
        "longitude": -76.502792,
        "source": (
            "Newport News EDA AirCommerce Park",
            "https://newportnewsva.com/business-neighborhoods/patrick-henry-corridor/",
        ),
    },
}

# The coordinate fallback is intentionally broad. These airport overrides keep
# well-known locality assignments from crossing adjacent ecosystem regions.
AIRPORT_REGION_OVERRIDES = {
    "2G6": "Greater Richmond",
    "CHO": "Central Virginia",
    "EZF": "Fredericksburg Region",
    "FRR": "Shenandoah Valley",
    "HSP": "Shenandoah Valley",
    "LYH": "Lynchburg Region",
    "MFV": "Eastern Shore",
    "MTV": "Southside Virginia",
    "RMN": "Fredericksburg Region",
    "ROA": "Roanoke Valley",
    "TGI": "Eastern Shore",
    "W24": "Lynchburg Region",
    "W90": "Lynchburg Region",
    "W91": "Roanoke Valley",
}

DEFENSE_INSTALLATIONS = [
    ("The Pentagon", "Arlington", "Northern Virginia"),
    ("Joint Base Myer-Henderson Hall", "Arlington", "Northern Virginia"),
    ("Army National Guard Readiness Center", "Arlington", "Northern Virginia"),
    ("Defense Advanced Research Projects Agency", "Arlington", "Northern Virginia"),
    ("Fort Belvoir", "Springfield", "Northern Virginia"),
    ("National Geospatial-Intelligence Agency Springfield", "Springfield", "Northern Virginia"),
    ("Marine Corps Base Quantico", "Quantico", "Northern Virginia"),
    ("Fort A.P. Hill", "Bowling Green", "Fredericksburg Region"),
    ("Naval Support Facility Dahlgren", "Dahlgren", "Fredericksburg Region"),
    ("Defense Supply Center Richmond", "Richmond", "Greater Richmond"),
    ("Fort Lee", "Prince George", "Greater Richmond"),
    ("Naval Weapons Station Yorktown", "Yorktown", "Hampton Roads"),
    ("Fort Eustis - Joint Base Langley-Eustis", "Newport News", "Hampton Roads"),
    ("Langley Air Force Base - Joint Base Langley-Eustis", "Hampton", "Hampton Roads"),
    ("Naval Station Norfolk", "Norfolk", "Hampton Roads"),
    ("Norfolk District, U.S. Army Corps of Engineers", "Norfolk", "Hampton Roads"),
    ("Naval Support Activity Hampton Roads", "Norfolk", "Hampton Roads"),
    ("Coast Guard Atlantic Area and Fifth Coast Guard District", "Portsmouth", "Hampton Roads"),
    ("Norfolk Naval Shipyard", "Portsmouth", "Hampton Roads"),
    ("Naval Medical Center Portsmouth", "Portsmouth", "Hampton Roads"),
    ("U.S. Coast Guard Base Portsmouth", "Portsmouth", "Hampton Roads"),
    ("Joint Expeditionary Base Little Creek-Fort Story", "Virginia Beach", "Hampton Roads"),
    ("Naval Air Station Oceana", "Virginia Beach", "Hampton Roads"),
    ("Dam Neck Annex", "Virginia Beach", "Hampton Roads"),
    ("Naval Support Activity Northwest Annex", "Chesapeake", "Hampton Roads"),
    ("Surface Combat Systems Center Wallops Island", "Wallops Island", "Eastern Shore"),
    ("Fort Pickett", "Blackstone", "Southside Virginia"),
    ("Rivanna Station", "Charlottesville", "Central Virginia"),
    ("The Judge Advocate General's Legal Center and School", "Charlottesville", "Central Virginia"),
    ("Radford Army Ammunition Plant", "Radford", "New River Valley"),
]

UNIVERSITY_ASSETS = [
    (
        "Virginia Tech",
        "Blacksburg",
        "New River Valley",
        "Public research university and institutional home of Virginia's FAA-designated UAS test-site team and a broad autonomy research network.",
        "university_vt",
        [
            "Mid-Atlantic Aviation Partnership",
            "Virginia Tech Drone Park",
            "Kentland Experimental Aerial Systems Laboratory",
            "Virginia Tech Advanced Control Systems Lab",
            "Center for Unmanned Aircraft Systems at Virginia Tech",
            "Virginia Tech Autonomous Systems and Control Laboratory",
            "Virginia Tech Transportation Institute",
            "Virginia Smart Road",
            "Virginia Automated Corridors",
            "Virginia Tech Center for Marine Autonomy and Robotics",
            "AutoBoat at Virginia Tech",
            "Virginia Tech Autonomy and Robotics",
            "Virginia Tech Hume Center for National Security and Technology",
            "Virginia Tech MADE",
            "Commonwealth Cyber Initiative",
            "Virginia Tech Grain Crop Drone Research Program",
            "Virginia Tech Eastern Shore AREC Drone Application Research",
            "Virginia Tech Counter UAS Research and Testing Center",
            "Virginia Tech Uncrewed Systems Laboratory",
            "Autonomous Aerial Vehicles at Virginia Tech",
            "Virginia Tech SpaceDrones Laboratory",
            "Virginia Tech Mission Systems Division",
            "Virginia Tech RoboGrinder",
            "Virginia Tech GobbleBot Autonomous Delivery Robot",
        ],
    ),
    (
        "University of Virginia",
        "Charlottesville",
        "Central Virginia",
        "Public research university represented by mapped robotics, autonomous-systems, embedded-systems, and institutional UAS activities.",
        "university_uva",
        [
            "UVA Link Lab",
            "UVA Robotics and Autonomous Systems Research",
            "UVA Robotics, Dynamics, and Autonomous Systems",
            "Cavalier Autonomous Racing",
            "UVA Bio-Inspired Engineering Research Laboratory",
            "UVA Robotics and Embedded Systems Focus Path",
            "University of Virginia UAS Operations Program",
            "UVA Coastal Research Center UAS Operations",
        ],
    ),
    (
        "Virginia Commonwealth University",
        "Richmond",
        "Greater Richmond",
        "Public research university represented by autonomous-vehicle, robotics, UAV research, and institutional flight-operations records.",
        "university_vcu",
        [
            "VCU Autonomous Robots and Vehicles Laboratory",
            "VCU Robotics and Autonomous Systems Group",
            "VCU UAV Research Laboratory",
            "Virginia Commonwealth University UAS Operations Program",
            "VCU Robotics and Autonomous Systems Engineering BS",
        ],
    ),
    (
        "Old Dominion University",
        "Norfolk",
        "Hampton Roads",
        "Public research university with mapped autonomy, modeling and simulation, spaceflight, education, and UAS operations capabilities.",
        "university_odu",
        [
            "ODU Unmanned and Autonomous Vehicle Laboratory",
            "Virginia Modeling, Analysis and Simulation Center",
            "Virginia Institute for Spaceflight and Autonomy",
            "Virginia Space Grant Consortium Drone Academies",
            "Old Dominion University UAS Operations Program",
        ],
    ),
    (
        "Christopher Newport University",
        "Newport News",
        "Hampton Roads",
        "Public university represented by mapped research laboratories for autonomous aerial and ground systems and humanitarian robotics.",
        "university_cnu",
        [
            "CNU Autonomous Systems and Drone Lab",
            "CNU Capable Humanitarian Robotics and Intelligent Systems Lab",
        ],
    ),
    (
        "George Mason University",
        "Fairfax",
        "Northern Virginia",
        "Public research university represented by mapped robotics, air-transportation systems, and public-safety UAS activities.",
        "university_gmu",
        [
            "George Mason Autonomous Robotics Laboratory",
            "George Mason Center for Air Transportation Systems Research",
            "George Mason University Police UAS Team",
            "George Mason Starship Autonomous Delivery Fleet",
            "George Mason SPARX",
            "George Mason MICO Laboratory",
            "George Mason RobotiXX Laboratory",
            "Mason Innovation Exchange Autonomous Systems Short Courses",
            "George Mason Northern Virginia DFR Planning Study",
        ],
    ),
    (
        "James Madison University",
        "Harrisonburg",
        "Shenandoah Valley",
        "Public university represented by mapped interdisciplinary facilities and project-based drone education.",
        "university_jmu",
        ["JMU X-Labs", "JMU Drone Challenge"],
    ),
    (
        "Liberty University",
        "Lynchburg",
        "Lynchburg Region",
        "Private university represented by mapped aeronautics programs in unmanned-aircraft operations and maintenance.",
        "university_liberty",
        [
            "Liberty University School of Aeronautics",
            "Liberty University Aeronautics: Unmanned Aerial Systems BS",
            "Liberty University Aviation Maintenance: Unmanned Aerial Systems BS",
            "Liberty University Medium Unmanned Aerial Systems Certificate",
            "Liberty University UAS Operational Experience",
        ],
    ),
    (
        "Virginia State University",
        "Petersburg",
        "Greater Richmond",
        "Public university represented by a mapped institutional process for approved unmanned-aircraft research and operations.",
        "university_vsu",
        ["Virginia State University UAS Operations Program"],
    ),
    (
        "William & Mary",
        "Williamsburg",
        "Hampton Roads",
        "Public research university and institutional home of the Virginia Institute of Marine Science and its coastal research capabilities.",
        "university_wm",
        ["Virginia Institute of Marine Science"],
    ),
    (
        "Hampton University",
        "Hampton",
        "Hampton Roads",
        "Private university with a documented UAS degree concentration, pilot training, applied operations, and autonomy research.",
        "university_hampton",
        ["Hampton University Uncrewed Aircraft Systems Program"],
    ),
    (
        "Radford University",
        "Radford",
        "New River Valley",
        "Public university with a documented interdisciplinary minor and coursework in unmanned aerial systems.",
        "university_radford",
        ["Radford University Unmanned Aerial Systems Minor"],
    ),
    (
        "Virginia Military Institute",
        "Lexington",
        "Shenandoah Valley",
        "Public military college represented by documented cadet research in drone detection and counter-UAS sensing.",
        "university_vmi",
        ["VMI Drone Detection and Counter-UAS Research"],
    ),
    (
        "Norfolk State University",
        "Norfolk",
        "Hampton Roads",
        "Public research university with documented tactical-autonomy research and applied drone coursework.",
        "university_nsu",
        [
            "Norfolk State Tactical Autonomy Research Program",
            "Norfolk State Drone Photography Course",
        ],
    ),
    (
        "Shenandoah University",
        "Winchester",
        "Shenandoah Valley",
        "Private university represented by a documented immersive drone-assembly training project.",
        "university_shenandoah",
        ["Shenandoah Drone Assembly VR Training"],
    ),
    (
        "Longwood University",
        "Farmville",
        "Central Virginia",
        "Public university represented by a documented autonomous-marine entrepreneurship and prototyping project.",
        "university_longwood",
        ["Longwood SEED Autonomous Marine Project"],
    ),
    (
        "Emory & Henry University",
        "Emory",
        "Southwest Virginia",
        "Private university offering documented drone operations and FAA remote-pilot test preparation coursework.",
        "university_ehc",
        ["Emory & Henry Drone Pilot Test Preparation"],
    ),
    (
        "Richard Bland College",
        "South Prince George",
        "Greater Richmond",
        "Public college with a documented UAS certificate and an applied critical-infrastructure autonomy center.",
        "university_rbc",
        [
            "Richard Bland College Uncrewed Aerial Systems Certificate",
            "Energy-Centric UAS Center for Critical Infrastructure",
        ],
    ),
    (
        "University of Virginia's College at Wise",
        "Wise",
        "Southwest Virginia",
        "Public liberal-arts college represented by a regional robotics, drone, coding, and autonomous-systems outreach program.",
        "university_uvawise",
        ["UVA Wise STREAMWISE Robot Drone League"],
    ),
]

CURATED_ASSETS = [
    # Virginia Tech and New River Valley research/test assets.
    (
        "Mid-Atlantic Aviation Partnership",
        "organization",
        "Blacksburg",
        "New River Valley",
        "research_air",
        "FAA-designated UAS test-site organization managed by Virginia Tech.",
        "vedp",
    ),
    (
        "Virginia Tech Drone Park",
        "facility",
        "Blacksburg",
        "New River Valley",
        "research_air",
        "Netted flight facility supporting university UAS instruction, research, and operations.",
        "vedp",
    ),
    (
        "Kentland Experimental Aerial Systems Laboratory",
        "facility",
        "Blacksburg",
        "New River Valley",
        "research_air",
        "Virginia Tech field laboratory for UAS flight dynamics, control, research, and instruction.",
        "vt_keas",
    ),
    (
        "Virginia Tech Advanced Control Systems Lab",
        "facility",
        "Blacksburg",
        "New River Valley",
        "research_air",
        "Indoor research hangar for autonomous aerial and ground robot control experiments.",
        "vt_acsl",
    ),
    (
        "Center for Unmanned Aircraft Systems at Virginia Tech",
        "organization",
        "Blacksburg",
        "New River Valley",
        "research_air",
        "University research center focused on unmanned-aircraft-system technologies and applications.",
        "vedp",
    ),
    (
        "Virginia Tech Autonomous Systems and Control Laboratory",
        "facility",
        "Blacksburg",
        "New River Valley",
        "research_air",
        "Research laboratory for control, estimation, and autonomous-system design.",
        "vedp",
    ),
    (
        "Virginia Tech Transportation Institute",
        "organization",
        "Blacksburg",
        "New River Valley",
        "research_ground",
        "Transportation research institute operating connected and automated vehicle research programs.",
        "vedp",
    ),
    (
        "Virginia Smart Road",
        "operating-environment",
        "Blacksburg",
        "New River Valley",
        "research_ground",
        "Controlled transportation test facility used for connected and automated vehicle research.",
        "vedp",
    ),
    (
        "Virginia Automated Corridors",
        "operating-environment",
        "Fairfax",
        "Northern Virginia",
        "research_ground",
        "Northern Virginia road network and test environments supporting automated-vehicle development.",
        "vedp",
    ),
    (
        "Virginia Tech Center for Marine Autonomy and Robotics",
        "organization",
        "Blacksburg",
        "New River Valley",
        "research_marine",
        "Interdisciplinary center developing autonomous marine vehicles, navigation, control, and multi-agent systems.",
        "vt_marine",
    ),
    (
        "AutoBoat at Virginia Tech",
        "program",
        "Blacksburg",
        "New River Valley",
        "research_marine",
        "Student engineering team designing fully autonomous robotic sailboats and electric motorboats.",
        "vt_autoboat",
    ),
    (
        "Virginia Tech Autonomy and Robotics",
        "organization",
        "Blacksburg",
        "New River Valley",
        "research_ground",
        "University-wide network connecting autonomous-systems and robotics research groups.",
        "vedp",
    ),
    (
        "Autonomous Aerial Vehicles at Virginia Tech",
        "program",
        "Blacksburg",
        "New River Valley",
        "research_air",
        "Student engineering team developing autonomous aircraft for payload delivery, obstacle avoidance, mapping, and search and rescue.",
        "vt_aav",
    ),
    (
        "Virginia Tech SpaceDrones Laboratory",
        "facility",
        "Blacksburg",
        "New River Valley",
        "research_air",
        "Collaborative hardware and software laboratory for autonomous space applications, distributed UAS, and vision-based tracking.",
        "vt_spacedrones",
    ),
    (
        "Virginia Tech Mission Systems Division",
        "organization",
        "Blacksburg",
        "New River Valley",
        "research_air",
        "National-security research division developing autonomous platforms, resilient control, maritime sensing, and airborne and spaceborne systems.",
        "vt_mission_systems",
    ),
    (
        "Virginia Tech RoboGrinder",
        "program",
        "Blacksburg",
        "New River Valley",
        "research_ground",
        "Student design team building terrestrial and aerial robots for tele-operated and fully autonomous RoboMaster competition missions.",
        "vt_idpro",
    ),
    (
        "Virginia Tech GobbleBot Autonomous Delivery Robot",
        "program",
        "Blacksburg",
        "New River Valley",
        "research_ground",
        "Student project developing an autonomous food-delivery robot and the supporting engineering and commercialization pathway.",
        "vt_idpro",
    ),
    # University of Virginia.
    (
        "UVA Link Lab",
        "organization",
        "Charlottesville",
        "Central Virginia",
        "research_ground",
        "Cyber-physical systems research center with robotics, autonomy, sensing, and smart-systems programs.",
        "uva_robotics",
    ),
    (
        "UVA Robotics and Autonomous Systems Research",
        "program",
        "Charlottesville",
        "Central Virginia",
        "research_ground",
        "Research program spanning autonomous vehicles, drones, multi-robot systems, and human-robot interaction.",
        "uva_robotics",
    ),
    (
        "UVA Robotics, Dynamics, and Autonomous Systems",
        "program",
        "Charlottesville",
        "Central Virginia",
        "research_ground",
        "Mechanical and aerospace research area covering aerial, underwater, ground, and space autonomy.",
        "uva_maye",
    ),
    (
        "Cavalier Autonomous Racing",
        "program",
        "Charlottesville",
        "Central Virginia",
        "research_ground",
        "UVA autonomous-racing research and student team developing perception, planning, and control systems.",
        "uva_robotics",
    ),
    (
        "UVA Bio-Inspired Engineering Research Laboratory",
        "facility",
        "Charlottesville",
        "Central Virginia",
        "research_marine",
        "Research laboratory developing bio-inspired structures, controls, and aquatic robotic concepts.",
        "uva_maye",
    ),
    (
        "UVA Robotics and Embedded Systems Focus Path",
        "program",
        "Charlottesville",
        "Central Virginia",
        "workforce",
        "Engineering education path covering embedded systems, drones, robotics, communications, and cyber-physical systems.",
        "uva_ece",
    ),
    # VCU, ODU, CNU, GMU, and JMU.
    (
        "VCU Autonomous Robots and Vehicles Laboratory",
        "facility",
        "Richmond",
        "Greater Richmond",
        "research_ground",
        "Research laboratory for autonomous vehicles, coordinated robotics, sensing, control, and AI.",
        "vcu_arvl",
    ),
    (
        "VCU Robotics and Autonomous Systems Group",
        "organization",
        "Richmond",
        "Greater Richmond",
        "research_ground",
        "VCU engineering research group connecting robotics and autonomous-systems faculty and laboratories.",
        "vcu_arvl",
    ),
    (
        "VCU UAV Research Laboratory",
        "facility",
        "Richmond",
        "Greater Richmond",
        "research_air",
        "University UAV research capability documented for flight-control and payload-system research.",
        "vedp",
    ),
    (
        "ODU Unmanned and Autonomous Vehicle Laboratory",
        "facility",
        "Norfolk",
        "Hampton Roads",
        "research_air",
        "Old Dominion University laboratory supporting ground and flight autonomous-vehicle design.",
        "vedp",
    ),
    (
        "Virginia Modeling, Analysis and Simulation Center",
        "organization",
        "Suffolk",
        "Hampton Roads",
        "research_marine",
        "ODU research center with virtual-environment, robotics, and unmanned-surface-vehicle work.",
        "vedp",
    ),
    (
        "Virginia Institute for Spaceflight and Autonomy",
        "organization",
        "Norfolk",
        "Hampton Roads",
        "research_air",
        "ODU institute coordinating spaceflight, autonomous-systems research, education, and commercialization.",
        "vedp",
    ),
    (
        "CNU Autonomous Systems and Drone Lab",
        "facility",
        "Newport News",
        "Hampton Roads",
        "research_air",
        "Christopher Newport University lab researching safe control and planning for aerial and ground vehicles.",
        "vedp",
    ),
    (
        "CNU Capable Humanitarian Robotics and Intelligent Systems Lab",
        "facility",
        "Newport News",
        "Hampton Roads",
        "research_ground",
        "CNU lab developing verifiable autonomous robotic behaviors for human-support applications.",
        "vedp",
    ),
    (
        "George Mason Autonomous Robotics Laboratory",
        "facility",
        "Fairfax",
        "Northern Virginia",
        "research_ground",
        "Collaborative robotics research laboratory spanning computer vision, networks, and autonomous systems.",
        "vedp",
    ),
    (
        "George Mason Center for Air Transportation Systems Research",
        "organization",
        "Fairfax",
        "Northern Virginia",
        "research_air",
        "Research center focused on air transportation systems, operations, modeling, and analysis.",
        "vedp",
    ),
    (
        "George Mason Starship Autonomous Delivery Fleet",
        "program",
        "Fairfax",
        "Northern Virginia",
        "research_ground",
        "Operational campus fleet of autonomous sidewalk robots providing recurring food-delivery service at George Mason.",
        "gmu_starship",
    ),
    (
        "George Mason SPARX",
        "program",
        "Fairfax",
        "Northern Virginia",
        "research_ground",
        "Swarming Platform for Autonomous Robots X research program developing and testing coordinated low-cost robot teams.",
        "gmu_sparx",
    ),
    (
        "George Mason MICO Laboratory",
        "facility",
        "Fairfax",
        "Northern Virginia",
        "research_ground",
        "Laboratory researching control, optimization, and learning for multi-robot systems, autonomous driving, and human-robot teams.",
        "gmu_mico",
    ),
    (
        "George Mason RobotiXX Laboratory",
        "facility",
        "Arlington",
        "Northern Virginia",
        "research_ground",
        "Field-robotics laboratory developing motion-planning and machine-learning methods for robust mobile autonomy.",
        "gmu_robotixx",
    ),
    (
        "Mason Innovation Exchange Autonomous Systems Short Courses",
        "program",
        "Fairfax",
        "Northern Virginia",
        "workforce_robotics",
        "Hands-on short courses in drone prototyping, autonomous robotics, sensor integration, and lighter-than-air uncrewed vehicles.",
        "gmu_mix",
    ),
    (
        "George Mason Northern Virginia DFR Planning Study",
        "program",
        "Fairfax",
        "Northern Virginia",
        "research_air",
        "2025-26 regional simulation and optimization study evaluating drone-as-first-responder coverage and base locations across Northern Virginia.",
        "gmu_c5i_dfr",
    ),
    (
        "JMU X-Labs",
        "facility",
        "Harrisonburg",
        "Shenandoah Valley",
        "research_air",
        "Collaborative facility for interdisciplinary emerging-technology work, including drone courses and projects.",
        "vedp",
    ),
    (
        "JMU Drone Challenge",
        "program",
        "Harrisonburg",
        "Shenandoah Valley",
        "research_air",
        "Documented interdisciplinary project applying drone technology to complex public-interest problems.",
        "vedp",
    ),
    # NASA, Wallops, and statewide test infrastructure.
    (
        "NASA Langley Research Center",
        "organization",
        "Hampton",
        "Hampton Roads",
        "research_air",
        "NASA research center conducting autonomy, UAS airspace integration, sensing, and flight research.",
        "vedp",
    ),
    (
        "NASA Langley CERTAIN",
        "operating-environment",
        "Hampton",
        "Hampton Roads",
        "research_air",
        "City Environment for Range Testing of Autonomous Integrated Navigation at NASA Langley.",
        "nasa_certain",
    ),
    (
        "NASA Langley Autonomy Incubator",
        "organization",
        "Hampton",
        "Hampton Roads",
        "research_ground",
        "Multidisciplinary NASA group researching autonomy skills and reusable autonomous-system capabilities.",
        "vedp",
    ),
    (
        "NASA Wallops Flight Facility",
        "facility",
        "Wallops Island",
        "Eastern Shore",
        "research_air",
        "NASA flight facility supporting atmospheric, aerospace, UAS, and range operations.",
        "vedp",
    ),
    (
        "Mid-Atlantic Regional Spaceport",
        "facility",
        "Wallops Island",
        "Eastern Shore",
        "research_air",
        "Virginia spaceport providing launch, range, integration, and advanced-aerospace infrastructure.",
        "vedp",
    ),
    (
        "MARS Unmanned Aircraft Systems Airfield",
        "facility",
        "Wallops Island",
        "Eastern Shore",
        "research_air",
        "Purpose-built UAS airfield and VTOL test infrastructure at the Mid-Atlantic Regional Spaceport.",
        "vedp",
    ),
    (
        "Virginia International Raceway Automated Vehicle Test Environment",
        "operating-environment",
        "Danville",
        "Southside Virginia",
        "research_ground",
        "Road-course test environment identified by VEDP as part of Virginia's automated-vehicle ecosystem.",
        "vedp",
    ),
    # Workforce programs specifically documented by VEDP.
    (
        "Liberty University School of Aeronautics",
        "organization",
        "Lynchburg",
        "Lynchburg Region",
        "workforce",
        "Aeronautics school offering unmanned-aircraft education, operations, and maintenance pathways.",
        "vedp",
    ),
    (
        "Liberty University Aeronautics: Unmanned Aerial Systems BS",
        "program",
        "Lynchburg",
        "Lynchburg Region",
        "workforce",
        "Bachelor's degree pathway preparing students for UAS operations and aviation careers.",
        "vedp",
    ),
    (
        "Liberty University Aviation Maintenance: Unmanned Aerial Systems BS",
        "program",
        "Lynchburg",
        "Lynchburg Region",
        "workforce",
        "Bachelor's degree pathway focused on maintenance of unmanned aircraft systems.",
        "vedp",
    ),
    (
        "Mountain Empire Community College UAS Program",
        "program",
        "Wise",
        "Southwest Virginia",
        "workforce",
        "Community-college coursework and degree development in unmanned aircraft operations.",
        "vedp",
    ),
    (
        "New River Community College sUAS Remote Pilot Ground School",
        "program",
        "Christiansburg",
        "New River Valley",
        "workforce",
        "Ground-school course supporting small-UAS remote-pilot knowledge and certification preparation.",
        "vedp",
    ),
    (
        "Piedmont Virginia Community College sUAS Public Safety Courses",
        "program",
        "Charlottesville",
        "Central Virginia",
        "workforce",
        "Small-UAS coursework designed for emergency-services and public-safety applications.",
        "vedp",
    ),
    (
        "Germanna Community College Drone-UAV FAA Pilot Class",
        "program",
        "Dahlgren",
        "Fredericksburg Region",
        "workforce",
        "Community-college class supporting FAA remote-pilot knowledge for drone operations.",
        "vedp",
    ),
    (
        "Blue Ridge Community College Unmanned Systems Courses",
        "program",
        "Weyers Cave",
        "Shenandoah Valley",
        "workforce",
        "Community-college UMS coursework covering small-UAS operations, mission planning, and autonomous flight.",
        "vccs_brcc",
    ),
    (
        "Brightpoint Community College Unmanned Systems Courses",
        "program",
        "Chester",
        "Greater Richmond",
        "workforce",
        "Community-college small-UAS coursework supporting remote-pilot knowledge and operational skills.",
        "vccs_brightpoint",
    ),
    (
        "Danville Community College Unmanned Systems Courses",
        "program",
        "Danville",
        "Southside Virginia",
        "workforce",
        "Community-college UMS coursework covering small-UAS platforms, operations, and mission support.",
        "vccs_danville",
    ),
    (
        "Eastern Shore Community College Unmanned Systems Courses",
        "program",
        "Melfa",
        "Eastern Shore",
        "workforce",
        "Community-college UMS coursework supporting small-UAS operations and applied technical skills.",
        "vccs_escc",
    ),
    (
        "Laurel Ridge Community College Unmanned Systems Courses",
        "program",
        "Middletown",
        "Shenandoah Valley",
        "workforce",
        "Community-college UMS coursework including remote-pilot ground school and small-UAS operations.",
        "vccs_laurel",
    ),
    (
        "Mountain Gateway Community College Unmanned Systems Courses",
        "program",
        "Clifton Forge",
        "Shenandoah Valley",
        "workforce",
        "Community-college UMS coursework covering remote-pilot preparation and advanced UAS operations.",
        "vccs_mountain_gateway",
    ),
    (
        "Tidewater Community College Unmanned Systems Courses",
        "program",
        "Chesapeake",
        "Hampton Roads",
        "workforce",
        "Community-college UMS coursework covering remote-pilot knowledge and small-UAS operations.",
        "vccs_tcc",
    ),
    (
        "Virginia Highlands Community College Small UAS Certificate",
        "program",
        "Abingdon",
        "Southwest Virginia",
        "workforce",
        "Career Studies Certificate preparing students to integrate remote-pilot technologies and pursue Part 107 certification.",
        "vhcc_suas",
    ),
    (
        "Virginia Peninsula Community College Drone Flight Technician Certificate",
        "program",
        "Hampton",
        "Hampton Roads",
        "workforce",
        "Career Studies Certificate covering drone operation, autonomous flight, construction, maintenance, and Part 107 preparation.",
        "vpcc_drone",
    ),
    (
        "Virginia Community College System Unmanned Systems Curriculum",
        "program",
        "Richmond",
        "Greater Richmond",
        "workforce",
        "Statewide community-college UMS curriculum spanning remote-pilot ground school, operations, maintenance, imaging, and internships.",
        "vccs_system",
    ),
    (
        "Virginia Western Autonomous Vehicle Technology Certificate",
        "program",
        "Roanoke",
        "Roanoke Valley",
        "workforce_robotics",
        "Career Studies Certificate combining mechatronics with autonomous-vehicle operation, troubleshooting, robotics, and industry credentials.",
        "vwcc_autonomous",
    ),
    (
        "UVA Wise STREAMWISE Robot Drone League",
        "program",
        "Wise",
        "Southwest Virginia",
        "workforce_robotics",
        "Regional workforce-outreach program using drones, robots, coding, competitions, and a campus learning hub to build autonomous-systems skills.",
        "uvawise_streamwise",
    ),
    # Virginia unmanned-systems companies and documented programs.
    (
        "HII Unmanned Systems Center of Excellence",
        "facility",
        "Hampton",
        "Hampton Roads",
        "company_marine",
        "Digital manufacturing and engineering facility established for HII unmanned and autonomous systems.",
        "hii_uxs",
    ),
    (
        "Longbow Unmanned Systems Research and Test Center",
        "operating-environment",
        "Hampton",
        "Hampton Roads",
        "test_multi",
        "Fort Monroe center supporting urban air, ground, and maritime unmanned-system research, testing, and validation.",
        "longbow",
    ),
    (
        "Advanced Aircraft Company",
        "organization",
        "Hampton",
        "Hampton Roads",
        "company_air",
        "Hampton developer and manufacturer of long-endurance hybrid-electric unmanned aircraft systems.",
        "aac",
    ),
    (
        "Adaptive Aerospace Group",
        "organization",
        "Hampton",
        "Hampton Roads",
        "company_air",
        "Hampton aerospace engineering company providing uncrewed-aircraft-system design and technical services.",
        "adaptive",
    ),
    (
        "RapidFlight UAS Manufacturing Headquarters",
        "facility",
        "Manassas",
        "Northern Virginia",
        "company_air",
        "Manassas headquarters and digital manufacturing facility for rapidly produced unmanned aircraft systems.",
        "rapidflight",
    ),
    (
        "Xelevate Leesburg Unmanned Systems Facility",
        "operating-environment",
        "Leesburg",
        "Northern Virginia",
        "test_multi",
        "Dedicated Loudoun County facility for unmanned-systems testing, development, training, and demonstrations.",
        "xelevate",
    ),
    (
        "Virginia UAS",
        "organization",
        "Glen Allen",
        "Greater Richmond",
        "company_air",
        "Virginia small-UAS training, safety, operational integration, and consulting provider.",
        "virginia_uas",
    ),
    (
        "AeroVironment Corporate Headquarters",
        "organization",
        "Arlington",
        "Northern Virginia",
        "company_cross",
        "Arlington headquarters of a multi-domain autonomous-systems, UAS, UGV, counter-UAS, and robotics company.",
        "aerovironment",
    ),
    (
        "QinetiQ US Headquarters",
        "organization",
        "Lorton",
        "Northern Virginia",
        "company_cross",
        "Lorton headquarters of a company providing multi-domain autonomous systems and unmanned robotic platforms.",
        "qinetiq",
    ),
    (
        "Dedrone Washington-Area Headquarters",
        "organization",
        "Sterling",
        "Northern Virginia",
        "company_cross",
        "Sterling headquarters for counter-drone sensing, identification, tracking, and airspace-security technology.",
        "dedrone",
    ),
    (
        "DroneUp",
        "organization",
        "Virginia Beach",
        "Hampton Roads",
        "company_air",
        "Virginia Beach-founded drone services, operations, software, training, and delivery company.",
        "vedp_companies",
    ),
    (
        "HUSH Aerospace",
        "organization",
        "Virginia Beach",
        "Hampton Roads",
        "company_air",
        "Virginia company providing UAS product design, prototyping, analysis, and manufacturing.",
        "vedp_companies",
    ),
    (
        "Perrone Robotics",
        "organization",
        "Charlottesville",
        "Central Virginia",
        "company_ground",
        "Developer of autonomous retrofit systems for transit and other vehicle platforms.",
        "vedp_companies",
    ),
    (
        "Torc Robotics",
        "organization",
        "Blacksburg",
        "New River Valley",
        "company_ground",
        "Autonomous-trucking technology company founded in Blacksburg and part of Daimler Truck.",
        "vedp",
    ),
    (
        "Aurora Flight Sciences",
        "organization",
        "Manassas",
        "Northern Virginia",
        "company_air",
        "Aerospace company developing advanced aircraft and autonomous flight technologies in Manassas.",
        "vedp",
    ),
    (
        "Aeroprobe",
        "organization",
        "Christiansburg",
        "New River Valley",
        "company_air",
        "Christiansburg aerospace company providing airflow measurement and advanced flight-test instrumentation.",
        "vedp",
    ),
    (
        "Dynamic Aviation",
        "organization",
        "Harrisonburg",
        "Shenandoah Valley",
        "company_air",
        "Virginia aviation operator and integrator with aircraft modification, mission, and fleet capabilities.",
        "vedp",
    ),
    (
        "Volvo Trucks New River Valley Plant",
        "facility",
        "Christiansburg",
        "New River Valley",
        "company_ground",
        "Truck manufacturing facility connected to Volvo autonomous-truck development documented by VEDP.",
        "vedp",
    ),
    (
        "ATA Aviation",
        "organization",
        "Fairfax",
        "Northern Virginia",
        "company_air",
        "Aviation systems and integration company leading work in Virginia's AAM test-site initiative.",
        "vipc_test",
    ),
    (
        "Dominion Energy UAS Program",
        "program",
        "Richmond",
        "Greater Richmond",
        "company_air",
        "Utility UAS activity supporting infrastructure inspection and Virginia advanced-flight demonstrations.",
        "vedp",
    ),
    (
        "Wing Christiansburg Drone Delivery Program",
        "program",
        "Christiansburg",
        "New River Valley",
        "company_air",
        "Documented commercial drone-delivery program launched in Christiansburg in 2019.",
        "vedp",
    ),
    (
        "Newport News Shipbuilding",
        "facility",
        "Newport News",
        "Hampton Roads",
        "company_marine",
        "Major Virginia shipyard providing naval engineering, digital shipbuilding, manufacturing, and integration capacity.",
        "vedp",
    ),
    (
        "Lockheed Martin Rotary and Mission Systems - Manassas",
        "facility",
        "Manassas",
        "Northern Virginia",
        "company_marine",
        "Virginia engineering site supporting maritime, undersea, sensing, and mission-system technologies.",
        "vedp",
    ),
    # State coordination and industry organizations.
    (
        "Virginia Unmanned Systems Center",
        "organization",
        "Richmond",
        "Greater Richmond",
        "state",
        "Statewide nexus for Virginia activity across land, air, sea, space, and advanced air mobility.",
        "vipc",
    ),
    (
        "Virginia Innovation Partnership Corporation",
        "organization",
        "Richmond",
        "Greater Richmond",
        "state",
        "Commonwealth innovation organization supporting grants, partnerships, commercialization, and seed funding.",
        "vipc",
    ),
    (
        "Virginia Advanced Air Mobility Alliance",
        "organization",
        "Richmond",
        "Greater Richmond",
        "aam_program",
        "Statewide alliance convening advanced-air-mobility and unmanned-systems stakeholders.",
        "vipc",
    ),
    (
        "Virginia Public Safety Innovation Center",
        "organization",
        "Richmond",
        "Greater Richmond",
        "state",
        "VIPC center connecting public-safety users with emerging technology, demonstrations, and research.",
        "vipc",
    ),
    (
        "Virginia Department of Aviation",
        "organization",
        "Richmond",
        "Greater Richmond",
        "aam_program",
        "Commonwealth aviation agency leading aviation planning and advanced-air-mobility initiatives.",
        "vipc_test",
    ),
    (
        "Virginia Department of Transportation UAS Program",
        "program",
        "Richmond",
        "Greater Richmond",
        "state",
        "State transportation program governing and supporting UAS use for transportation missions.",
        "vipc",
    ),
    (
        "Virginia State Police UAS Program",
        "program",
        "Richmond",
        "Greater Richmond",
        "public_safety",
        "State police drone program supporting crash and crime-scene mapping, searches, inspection, and specialized operations.",
        "vsp_uas",
    ),
    (
        "Virginia Conservation Police UAS Program",
        "program",
        "Henrico",
        "Greater Richmond",
        "public_safety",
        "Department of Wildlife Resources program using UAS for conservation-police and public-safety missions.",
        "dwr_uas",
    ),
    (
        "Virginia Department of Forestry UAV Program",
        "program",
        "Charlottesville",
        "Central Virginia",
        "public_safety",
        "State forestry drone program supporting wildfire response, incident management, mapping, and natural-resource missions.",
        "dof_uas",
    ),
    (
        "Virginia First Responder Unmanned Aircraft Trade and Replace Program",
        "program",
        "Richmond",
        "Greater Richmond",
        "public_safety",
        "DCJS grant program supporting Virginia first responders replacing qualifying unmanned aircraft with compliant systems.",
        "dcjs_drone",
    ),
    (
        "Virginia Advanced Air Mobility Program",
        "program",
        "Richmond",
        "Greater Richmond",
        "aam_program",
        "Commonwealth aviation program covering automated small uncrewed systems, remotely controlled aircraft, and aviation automation.",
        "doav_aam",
    ),
    (
        "Virginia Flight Information Exchange",
        "program",
        "Richmond",
        "Greater Richmond",
        "aam_program",
        "Statewide information-sharing capability supporting safe and informed UAS operations.",
        "virginia_fix",
    ),
    (
        "FAA BEYOND Virginia Team",
        "program",
        "Blacksburg",
        "New River Valley",
        "state",
        "Virginia team advancing scalable beyond-visual-line-of-sight UAS operations and safety cases.",
        "vedp",
    ),
    (
        "Association for Uncrewed Vehicle Systems International",
        "organization",
        "Arlington",
        "Northern Virginia",
        "state",
        "International unmanned-systems industry association headquartered in Arlington.",
        "vedp",
    ),
    (
        "AUVSI Hampton Roads Chapter",
        "organization",
        "Norfolk",
        "Hampton Roads",
        "state",
        "Regional industry chapter connecting unmanned-systems stakeholders in Hampton Roads.",
        "vedp",
    ),
    (
        "AUVSI Ridge and Valley Chapter",
        "organization",
        "Blacksburg",
        "New River Valley",
        "state",
        "Regional AUVSI chapter connecting uncrewed-systems research, testing, manufacturing, and industry stakeholders.",
        "auvsi_ridge",
    ),
    # Port and intermodal infrastructure.
    (
        "The Port of Virginia",
        "organization",
        "Norfolk",
        "Hampton Roads",
        "port",
        "Virginia port authority and terminal network supporting maritime and intermodal logistics.",
        "port",
    ),
    (
        "Norfolk International Terminals",
        "infrastructure",
        "Norfolk",
        "Hampton Roads",
        "port",
        "Large semi-automated container terminal with on-dock rail and interstate access.",
        "port",
    ),
    (
        "Virginia International Gateway",
        "infrastructure",
        "Portsmouth",
        "Hampton Roads",
        "port",
        "Semi-automated container terminal with rail, highway, and deep-water access.",
        "port",
    ),
    (
        "Portsmouth Marine Terminal",
        "infrastructure",
        "Portsmouth",
        "Hampton Roads",
        "port",
        "Marine terminal being used as an offshore-wind logistics and staging hub.",
        "port",
    ),
    (
        "Newport News Marine Terminal",
        "infrastructure",
        "Newport News",
        "Hampton Roads",
        "port",
        "Breakbulk, roll-on/roll-off, warehouse, rail, and heavy-lift marine terminal.",
        "port",
    ),
    (
        "Richmond Marine Terminal",
        "infrastructure",
        "Richmond",
        "Greater Richmond",
        "port",
        "James River terminal providing barge, warehouse, road, and rail logistics connections.",
        "port",
    ),
    (
        "Virginia Inland Port",
        "infrastructure",
        "Front Royal",
        "Shenandoah Valley",
        "port",
        "Intermodal rail terminal connecting inland markets to Hampton Roads container terminals.",
        "port",
    ),
    (
        "Craney Island Marine Terminal Project",
        "infrastructure",
        "Portsmouth",
        "Hampton Roads",
        "port",
        "Long-term port expansion and logistics infrastructure project in Hampton Roads.",
        "port",
    ),
    # Enabling research, manufacturing, communications, and commercialization capacity.
    (
        "Commonwealth Center for Advanced Manufacturing",
        "organization",
        "Prince George",
        "Greater Richmond",
        "enabling",
        "Applied research center for advanced manufacturing, automation, materials, and production systems.",
        "vedp",
    ),
    (
        "Institute for Advanced Learning and Research",
        "organization",
        "Danville",
        "Southside Virginia",
        "enabling",
        "Regional applied-research and workforce organization with advanced manufacturing and automation capacity.",
        "vedp",
    ),
    (
        "National Institute of Aerospace",
        "organization",
        "Hampton",
        "Hampton Roads",
        "enabling",
        "Research and graduate-education institute supporting aerospace engineering and NASA Langley collaborations.",
        "vedp",
    ),
    (
        "Virginia Tech Hume Center for National Security and Technology",
        "organization",
        "Blacksburg",
        "New River Valley",
        "enabling",
        "Research center for sensing, communications, autonomy, cybersecurity, and national-security technology.",
        "vedp",
    ),
    (
        "Virginia Tech MADE",
        "organization",
        "Blacksburg",
        "New River Valley",
        "enabling",
        "University advanced-manufacturing initiative including robotics, autonomous assembly, and field robotics.",
        "vt_made",
    ),
    (
        "Commonwealth Cyber Initiative",
        "organization",
        "Blacksburg",
        "New River Valley",
        "enabling",
        "Statewide research network for secure communications, cyber-physical systems, and next-generation networks.",
        "vedp",
    ),
    (
        "Virginia Institute of Marine Science",
        "organization",
        "Williamsburg",
        "Hampton Roads",
        "research_marine",
        "Marine science institute providing coastal research, field operations, sensing, and autonomous-platform context.",
        "vedp",
    ),
    (
        "Virginia Tech Grain Crop Drone Research Program",
        "program",
        "Blacksburg",
        "New River Valley",
        "agriculture",
        "Research program applying UAV imagery and analytics to crop health, nutrient response, biomass, and yield estimation.",
        "vt_grain_drones",
    ),
    (
        "Virginia Tech Eastern Shore AREC Drone Application Research",
        "program",
        "Melfa",
        "Eastern Shore",
        "agriculture",
        "Eastern Shore field research and outreach on agricultural drone sensing and spray-drone applications.",
        "vt_esarec_drones",
    ),
    (
        "Virginia Tech Counter UAS Research and Testing Center",
        "facility",
        "Blacksburg",
        "New River Valley",
        "counter_uas_research",
        "Research and testing center with outdoor, indoor, and virtual counter-UAS laboratories.",
        "vt_counter_uas",
    ),
    (
        "Virginia Tech Uncrewed Systems Laboratory",
        "facility",
        "Blacksburg",
        "New River Valley",
        "research_air",
        "University laboratory conducting uncrewed-system research, including autonomous aerial search applications.",
        "vt_usl",
    ),
    (
        "Fairfax County Unmanned Aircraft Systems Program",
        "program",
        "Fairfax",
        "Northern Virginia",
        "public_safety",
        "County program supporting public-safety missions including search and rescue, fire, hazmat, and damage assessment.",
        "fairfax_county_uas",
    ),
    (
        "George Mason University Police UAS Team",
        "program",
        "Fairfax",
        "Northern Virginia",
        "public_safety",
        "University police UAS team with publicly posted operational flight logs.",
        "gmu_police_uas",
    ),
    (
        "City of Virginia Beach UAS Program",
        "program",
        "Virginia Beach",
        "Hampton Roads",
        "public_safety",
        "Cross-department municipal UAS program supporting emergency operations and public-safety response.",
        "virginia_beach_uas",
    ),
    (
        "City of Fairfax Regional UAS Unit",
        "program",
        "Fairfax",
        "Northern Virginia",
        "public_safety",
        "Police participation in a regional UAS unit supporting documented public-safety operations.",
        "fairfax_city_uas",
    ),
    (
        "Virginia Space Grant Consortium Drone Academies",
        "program",
        "Hampton",
        "Hampton Roads",
        "workforce",
        "Drone-academy program delivering unmanned-systems education with Virginia community-college partners.",
        "vsgc_drone_academies",
    ),
    (
        "Virginia Commonwealth University UAS Operations Program",
        "program",
        "Richmond",
        "Greater Richmond",
        "institutional_uas",
        "Institutional UAS program governing and supporting research, instructional, and operational flights.",
        "vcu_uas",
    ),
    (
        "University of Virginia UAS Operations Program",
        "program",
        "Charlottesville",
        "Central Virginia",
        "institutional_uas",
        "University UAS operations program supporting compliant research, instruction, and approved flight activity.",
        "uva_uas",
    ),
    (
        "UVA Coastal Research Center UAS Operations",
        "facility",
        "Eastville",
        "Eastern Shore",
        "research_marine",
        "Coastal research-center UAS operations for compliant flights from the center's property and vessels.",
        "uva_crc_uas",
    ),
    (
        "Heven AeroTech Headquarters",
        "organization",
        "Dulles",
        "Northern Virginia",
        "company_air",
        "Virginia headquarters for a developer of hydrogen-powered and other unmanned aerial systems.",
        "heven",
    ),
    (
        "Agricision",
        "organization",
        "Sedley",
        "Hampton Roads",
        "company_agriculture",
        "Virginia agricultural-drone manufacturer providing scouting and spray drone platforms and software.",
        "agricision",
    ),
    (
        "Blue Ridge Defense Works",
        "organization",
        "Winchester",
        "Northern Virginia",
        "company_counter_uas",
        "Virginia counter-UAS company developing interceptor systems for defense applications.",
        "blue_ridge_defense",
    ),
    (
        "Zenith Aerotech",
        "organization",
        "Afton",
        "Central Virginia",
        "company_air",
        "Virginia manufacturer of tethered unmanned aircraft systems for public-safety, defense, and industrial applications.",
        "zenith",
    ),
    (
        "Old Dominion University UAS Operations Program",
        "program",
        "Norfolk",
        "Hampton Roads",
        "institutional_uas",
        "University operator-permit and flight-request program for UAS activity on university property.",
        "odu_uas",
    ),
    (
        "Virginia State University UAS Operations Program",
        "program",
        "Petersburg",
        "Greater Richmond",
        "institutional_uas",
        "University UAS oversight process for approved research, university-program, and campus flight activity.",
        "vsu_uas",
    ),
    (
        "Prince Edward County Emergency Management Drone Program",
        "program",
        "Farmville",
        "Central Virginia",
        "public_safety",
        "County emergency-management drone program maintained for documented public-safety operations.",
        "prince_edward_uas",
    ),
    (
        "Accomack County Emergency Management Drone Program",
        "program",
        "Accomac",
        "Eastern Shore",
        "public_safety",
        "County emergency-management drone program publicly presented through the Department of Public Safety.",
        "accomack_uas",
    ),
    (
        "Campbell County Sheriff's Office Drone Program",
        "program",
        "Rustburg",
        "Lynchburg Region",
        "public_safety",
        "Sheriff's Office drone program documented in the county's 2024 annual report.",
        "campbell_uas",
    ),
    # Additional source-backed education and workforce programs.
    (
        "Hampton University Uncrewed Aircraft Systems Program",
        "program",
        "Hampton",
        "Hampton Roads",
        "workforce",
        "Degree concentration, remote-pilot preparation, flight training, data services, and applied UAS research.",
        "hampton_uas",
    ),
    (
        "Radford University Unmanned Aerial Systems Minor",
        "program",
        "Radford",
        "New River Valley",
        "workforce",
        "Interdisciplinary minor covering UAS platforms, flight, applications, regulations, and data collection.",
        "radford_uas",
    ),
    (
        "VMI Drone Detection and Counter-UAS Research",
        "program",
        "Lexington",
        "Shenandoah Valley",
        "counter_uas_research",
        "Cadet research applying distributed acoustic sensing and machine learning to drone detection.",
        "vmi_counter_uas",
    ),
    (
        "Norfolk State Tactical Autonomy Research Program",
        "program",
        "Norfolk",
        "Hampton Roads",
        "research_air",
        "Federally funded research program developing artificial intelligence and autonomy for tactical systems.",
        "nsu_tactical_autonomy",
    ),
    (
        "Norfolk State Drone Photography Course",
        "program",
        "Norfolk",
        "Hampton Roads",
        "workforce",
        "Documented university course covering aerial image capture, drone operation, safety, and visual applications.",
        "nsu_drone_course",
    ),
    (
        "Shenandoah Drone Assembly VR Training",
        "program",
        "Winchester",
        "Shenandoah Valley",
        "workforce",
        "Immersive training project that teaches drone assembly and technical procedures in virtual reality.",
        "shenandoah_drone_vr",
    ),
    (
        "Longwood SEED Autonomous Marine Project",
        "program",
        "Farmville",
        "Central Virginia",
        "research_marine",
        "Student entrepreneurship project developing an autonomous marine craft and related field capabilities.",
        "longwood_seed",
    ),
    (
        "Emory & Henry Drone Pilot Test Preparation",
        "program",
        "Emory",
        "Southwest Virginia",
        "workforce",
        "Environmental-studies course covering drone operation and preparation for the FAA remote-pilot exam.",
        "ehc_drone",
    ),
    (
        "Richard Bland College Uncrewed Aerial Systems Certificate",
        "program",
        "South Prince George",
        "Greater Richmond",
        "workforce",
        "College certificate pathway in uncrewed aerial systems operations and applied skills.",
        "rbc_uas_certificate",
    ),
    (
        "Energy-Centric UAS Center for Critical Infrastructure",
        "facility",
        "South Prince George",
        "Greater Richmond",
        "test_multi",
        "Applied UAS center led by CCALS for energy and critical-infrastructure operations, training, and testing.",
        "rbc_uas_center",
    ),
    (
        "VCU Robotics and Autonomous Systems Engineering BS",
        "program",
        "Richmond",
        "Greater Richmond",
        "workforce",
        "Undergraduate engineering degree integrating robotics, artificial intelligence, controls, and autonomous systems.",
        "vcu_robotics_degree",
    ),
    (
        "Liberty University Medium Unmanned Aerial Systems Certificate",
        "program",
        "Lynchburg",
        "Lynchburg Region",
        "workforce",
        "Professional certificate pathway for medium UAS ground and flight operations.",
        "liberty_medium_uas",
    ),
    (
        "Liberty University UAS Operational Experience",
        "program",
        "Lynchburg",
        "Lynchburg Region",
        "workforce",
        "Applied flight and mission experience for students in Liberty's unmanned-aircraft programs.",
        "liberty_uas_experience",
    ),
    (
        "New College Institute",
        "organization",
        "Martinsville",
        "Southside Virginia",
        "workforce",
        "State-supported higher-education center with documented drone education and robotics workforce programs.",
        "nci",
    ),
    (
        "Harrowgate Drone Park",
        "operating-environment",
        "Chester",
        "Greater Richmond",
        "test_multi",
        "County-designated outdoor flying area for recreational drones and radio-controlled aircraft.",
        "harrowgate_drone_park",
    ),
    (
        "IALR AgBOT Precision Agriculture Program",
        "program",
        "Danville",
        "Southside Virginia",
        "agriculture",
        "Autonomous thermal and multispectral drone program supporting precision-agriculture field analysis.",
        "ialr_agbot",
    ),
    (
        "Southwest Virginia Drone Soccer Program",
        "program",
        "Abingdon",
        "Southwest Virginia",
        "workforce",
        "Regional education program using drone soccer to develop technical, teamwork, and career-readiness skills.",
        "swva_drone_soccer",
    ),
    (
        "GO TEC Automation and Robotics Talent Pathway",
        "program",
        "Danville",
        "Southside Virginia",
        "workforce",
        "Statewide middle-school talent pathway providing hands-on automation, robotics, manufacturing, and precision-agriculture modules.",
        "go_tec",
    ),
    # Additional Virginia companies and enabling organizations.
    (
        "Fulcrum Concepts",
        "organization",
        "Mattaponi",
        "Greater Richmond",
        "company_air",
        "Virginia UAS engineering, integration, fabrication, flight-test, and training company.",
        "fulcrum",
    ),
    (
        "ANRA Technologies",
        "organization",
        "Reston",
        "Northern Virginia",
        "company_air",
        "Virginia-based developer of uncrewed traffic management, fleet operations, and airspace services.",
        "anra",
    ),
    (
        "Auterion U.S. Headquarters",
        "organization",
        "Arlington",
        "Northern Virginia",
        "company_cross",
        "Arlington headquarters for an open autonomous-systems software and mission-computing company.",
        "auterion",
    ),
    (
        "Flying Ship Company",
        "organization",
        "Leesburg",
        "Northern Virginia",
        "company_marine",
        "Virginia developer of autonomous wing-in-ground-effect maritime cargo vehicles.",
        "flying_ship",
    ),
    (
        "Sentinel Robotic Solutions",
        "organization",
        "Wallops Island",
        "Eastern Shore",
        "company_air",
        "Wallops-based small business supporting UAS engineering, operations, training, and test activities.",
        "sentinel",
    ),
    (
        "Autonomous Flight Technologies",
        "organization",
        "Roanoke",
        "Roanoke Valley",
        "company_air",
        "Roanoke-based developer of unmanned aircraft, avionics, and autonomous-flight technologies.",
        "autonomous_flight",
    ),
    (
        "ICI Services",
        "organization",
        "Virginia Beach",
        "Hampton Roads",
        "company_marine",
        "Virginia Beach engineering company supporting Navy unmanned-surface-vehicle development and integration.",
        "ici_usv",
    ),
    (
        "Commonwealth Center for Advanced Logistics Systems",
        "organization",
        "Richmond",
        "Greater Richmond",
        "enabling",
        "Virginia applied-research center leading UAS work for energy and critical-infrastructure use cases.",
        "ccals",
    ),
    # Additional public-safety operators documented by Virginia localities.
    (
        "Spotsylvania Regional Public Safety UAS Program",
        "program",
        "Spotsylvania",
        "Fredericksburg Region",
        "public_safety",
        "Regional public-safety UAS capability supporting emergency response and participating agencies.",
        "spotsylvania_uas",
    ),
    (
        "Norfolk Police UAS Team",
        "program",
        "Norfolk",
        "Hampton Roads",
        "public_safety",
        "Police UAS team supporting documented public-safety and crime-reduction operations.",
        "norfolk_police_uas",
    ),
    (
        "Norfolk Harbor Patrol Drone Capability",
        "program",
        "Norfolk",
        "Hampton Roads",
        "public_safety",
        "Harbor Patrol aerial-drone capability for search, recovery, maritime safety, and environmental monitoring.",
        "norfolk_harbor_uas",
    ),
    (
        "Montgomery County Sheriff's Office UAS Team",
        "program",
        "Christiansburg",
        "New River Valley",
        "public_safety",
        "Sheriff's Office UAS team supporting searches, incident awareness, and regional public-safety response.",
        "montgomery_uas",
    ),
    (
        "Roanoke County Police UAV Team",
        "program",
        "Roanoke",
        "Roanoke Valley",
        "public_safety",
        "Police unmanned-aircraft team supporting special operations and incident response.",
        "roanoke_police_uas",
    ),
    (
        "Roanoke County Fire and Rescue Drone Program",
        "program",
        "Roanoke",
        "Roanoke Valley",
        "public_safety",
        "Fire and rescue drone capability supporting emergency assessment and response.",
        "roanoke_fire_uas",
    ),
    (
        "Winchester Emergency Management sUAS Program",
        "program",
        "Winchester",
        "Shenandoah Valley",
        "public_safety",
        "City emergency-management small UAS capability documented in the municipal budget.",
        "winchester_uas",
    ),
    (
        "Danville Life Saving Crew Drone Team",
        "program",
        "Danville",
        "Southside Virginia",
        "public_safety",
        "Volunteer rescue drone team supporting documented searches and emergency incidents in the Danville area.",
        "danville_uas",
    ),
    (
        "Leesburg Police UAS Team",
        "program",
        "Leesburg",
        "Northern Virginia",
        "public_safety",
        "Police UAS team supporting searches, tactical response, crash documentation, and incident awareness.",
        "leesburg_uas",
    ),
    (
        "Fredericksburg Police UAS Team",
        "program",
        "Fredericksburg",
        "Fredericksburg Region",
        "public_safety",
        "Police UAS team supporting emergency response, searches, investigations, and public safety.",
        "fredericksburg_uas",
    ),
    (
        "Fredericksburg Drone as First Responder Program",
        "program",
        "Fredericksburg",
        "Fredericksburg Region",
        "public_safety",
        "Documented drone-as-first-responder program providing remote aerial awareness for selected calls.",
        "fredericksburg_dfr",
    ),
    (
        "Augusta County Sheriff's Office Drone Team",
        "program",
        "Staunton",
        "Shenandoah Valley",
        "public_safety",
        "Sheriff's Office drone team supporting searches, investigations, and regional incident response.",
        "augusta_uas",
    ),
    (
        "Bedford County Sheriff's Office Drone Team",
        "program",
        "Bedford",
        "Lynchburg Region",
        "public_safety",
        "Sheriff's Office drone team documented for search and public-safety operations.",
        "bedford_uas",
    ),
    (
        "Charlottesville Police UAS Team",
        "program",
        "Charlottesville",
        "Central Virginia",
        "public_safety",
        "Police emergency-services UAS team supporting high-risk incidents and public-safety response.",
        "charlottesville_uas",
    ),
    (
        "York County ROVER Team",
        "program",
        "Yorktown",
        "Hampton Roads",
        "public_safety",
        "Joint fire and sheriff sUAS team supporting search, hazmat, tactical, storm, and emergency missions.",
        "york_rover",
    ),
    (
        "Mecklenburg County Sheriff's Office Drone Team",
        "program",
        "Boydton",
        "Southside Virginia",
        "public_safety",
        "Sheriff's Office drone capability documented for county law-enforcement operations.",
        "mecklenburg_uas",
    ),
    (
        "Newport News Police and Fire Drone Unit",
        "program",
        "Newport News",
        "Hampton Roads",
        "public_safety",
        "Joint public-safety drone unit supporting police, fire, search, assessment, and emergency operations.",
        "newport_news_uas",
    ),
    (
        "Prince William County Police sUAS Team",
        "program",
        "Manassas",
        "Northern Virginia",
        "public_safety",
        "Police small-UAS team supporting searches, tactical response, crash scenes, and public-safety missions.",
        "prince_william_uas",
    ),
    (
        "Chesterfield Police Drone as First Responder Program",
        "program",
        "Chester",
        "Greater Richmond",
        "public_safety",
        "Police drone-as-first-responder capability supporting remote incident assessment and response.",
        "chesterfield_dfr",
    ),
    (
        "Chesterfield Fire and EMS sUAS Program",
        "program",
        "Chester",
        "Greater Richmond",
        "public_safety",
        "Fire and EMS small-UAS program supporting incident command, search, hazard, and damage assessment.",
        "chesterfield_fire_uas",
    ),
    (
        "Henrico Fire Robotics Response Team",
        "program",
        "Henrico",
        "Greater Richmond",
        "public_safety",
        "Fire specialty team using aerial and ground robotic systems for hazardous and complex incidents.",
        "henrico_robotics",
    ),
    (
        "Arlington Joint Public Safety UAS Program",
        "program",
        "Arlington",
        "Northern Virginia",
        "public_safety",
        "Joint county police, fire, and emergency-management UAS capability for approved public-safety missions.",
        "arlington_uas",
    ),
    (
        "Albemarle County Police UAS Program",
        "program",
        "Charlottesville",
        "Central Virginia",
        "public_safety",
        "County police drone capability documented for public-safety response and operations.",
        "albemarle_police_uas",
    ),
    (
        "Albemarle County Fire Rescue UAS Program",
        "program",
        "Charlottesville",
        "Central Virginia",
        "public_safety",
        "County fire-rescue UAS capability documented for fire investigation and emergency operations.",
        "albemarle_fire_uas",
    ),
    (
        "Loudoun County Sheriff's Office Drone Unit",
        "program",
        "Leesburg",
        "Northern Virginia",
        "public_safety",
        "Sheriff's Office drone unit supporting searches, Project Lifesaver, and public-safety response.",
        "loudoun_uas",
    ),
    (
        "Lynchburg Fire Department UAV Team",
        "program",
        "Lynchburg",
        "Lynchburg Region",
        "public_safety",
        "Fire department UAV team with thermal imaging for fire, hazmat, search, and technical-rescue calls.",
        "lynchburg_fire_uas",
    ),
    (
        "Lynchburg Police Drone Unit",
        "program",
        "Lynchburg",
        "Lynchburg Region",
        "public_safety",
        "Police drone unit documented for municipal law-enforcement and incident-response operations.",
        "lynchburg_police_uas",
    ),
    (
        "Harrisonburg Police and Fire Drone and Robot Unit",
        "program",
        "Harrisonburg",
        "Shenandoah Valley",
        "public_safety",
        "Joint police and fire unit operating drones and robots for law enforcement, fire, rescue, hazmat, and regional support.",
        "harrisonburg_uas",
    ),
    (
        "Suffolk Police UAS Unit",
        "program",
        "Suffolk",
        "Hampton Roads",
        "public_safety",
        "Police UAS unit supporting documented law-enforcement and public-safety operations.",
        "suffolk_uas",
    ),
    (
        "Richmond Police sUAV Program",
        "program",
        "Richmond",
        "Greater Richmond",
        "public_safety",
        "Police small-UAV program governed for emergency and exigent public-safety deployments.",
        "richmond_police_uas",
    ),
    (
        "James City County Police Drone as First Responder Program",
        "program",
        "Williamsburg",
        "Hampton Roads",
        "public_safety",
        "Police DFR test and operations program providing incident-based aerial awareness and supporting research into drone-delivered AEDs.",
        "james_city_dfr",
    ),
    (
        "Hanover County Sheriff's Office sUAS Team",
        "program",
        "Hanover",
        "Greater Richmond",
        "public_safety",
        "Sheriff's Office team supporting missing-person searches, crash documentation, situational awareness, and high-risk missions.",
        "hanover_uas",
    ),
    (
        "Culpeper Police Department Drone Team",
        "program",
        "Culpeper",
        "Central Virginia",
        "public_safety",
        "Municipal police drone team supporting searches, fire response, tactical incidents, investigations, and regional mutual aid.",
        "culpeper_uas",
    ),
    (
        "Orange County Sheriff's Office Drone Team",
        "program",
        "Orange",
        "Central Virginia",
        "public_safety",
        "Sheriff's Office drone team documented in a 2026 regional deployment supporting a search for fleeing armed subjects.",
        "orange_uas",
    ),
    # Federal autonomy research and engineering facilities.
    (
        "Naval Surface Warfare Center Dahlgren Division",
        "organization",
        "Dahlgren",
        "Fredericksburg Region",
        "federal_autonomy",
        "Navy warfare center with publicly documented unmanned-systems research, engineering, ranges, and test facilities.",
        "nswc_dahlgren",
    ),
    (
        "NSWC Dahlgren Outdoor Autonomy Laboratory",
        "facility",
        "Dahlgren",
        "Fredericksburg Region",
        "federal_autonomy",
        "Outdoor laboratory for ground, surface, undersea, radio-frequency, and cross-domain autonomy experimentation.",
        "dahlgren_autonomy_lab",
    ),
    (
        "NSWC Carderock Combatant Craft Division",
        "organization",
        "Norfolk",
        "Hampton Roads",
        "federal_autonomy",
        "Navy center for combatant-craft and unmanned-surface-vehicle engineering, design, integration, and evaluation.",
        "carderock_ccd",
    ),
    (
        "Marine Corps Warfighting Laboratory",
        "organization",
        "Quantico",
        "Northern Virginia",
        "federal_autonomy",
        "Marine Corps experimentation organization with documented autonomous reconnaissance and unmanned-systems activities.",
        "mcwl",
    ),
]

# Additional current assets verified against agency, university, company, or grant
# records. Multi-source entries retain both the operational source and the statewide
# award or ecosystem source that independently supports the record.
CURATED_ASSETS.extend(
    [
        (
            "Caroline County Fire and Rescue UAS Program",
            "program",
            "Bowling Green",
            "Fredericksburg Region",
            "public_safety",
            "County fire-rescue program operating a drone for search and rescue, damage assessment, situational awareness, and emergency response.",
            ("caroline_uas", "dcjs_awards"),
        ),
        (
            "Gloucester County Sheriff's Office UAS Program",
            "program",
            "Gloucester",
            "Hampton Roads",
            "public_safety",
            "Sheriff's Office UAS capability documented by a CY 2026 replacement award naming the project director at the Sheriff's Office.",
            ("gloucester_uas", "dcjs_awards"),
        ),
        (
            "Colonial Heights Police Drone Program",
            "program",
            "Colonial Heights",
            "Greater Richmond",
            "public_safety",
            "Police drone program documented through a current municipal replacement appropriation and statewide award record.",
            ("colonial_heights_uas", "dcjs_awards"),
        ),
        (
            "Hampton Joint Police and Fire UAS Unit",
            "program",
            "Hampton",
            "Hampton Roads",
            "public_safety",
            "Joint city UAS capability governed for police, fire, rescue, emergency-management, and public-safety missions.",
            ("hampton_joint_uas", "dcjs_awards"),
        ),
        (
            "Henry County Sheriff's Office Drone Program",
            "program",
            "Martinsville",
            "Southside Virginia",
            "public_safety",
            "Sheriff's Office drone program documented through the county's CY 2026 replacement-grant authorization.",
            ("henry_uas", "dcjs_awards"),
        ),
        (
            "Hopewell Fire and EMS Drone Program",
            "program",
            "Hopewell",
            "Greater Richmond",
            "public_safety",
            "Fire and EMS emergency-management drone program supporting fire, hazmat, search-and-rescue, and incident-awareness missions.",
            ("hopewell_uas", "dcjs_awards"),
        ),
        (
            "King George County Public Safety Drone Program",
            "program",
            "King George",
            "Fredericksburg Region",
            "public_safety",
            "County public-safety drone capability documented for fire-scene work, thermal training, and missing-person response.",
            ("king_george_uas", "dcjs_awards"),
        ),
        (
            "Stafford County Sheriff's Office UAS Team",
            "program",
            "Stafford",
            "Fredericksburg Region",
            "public_safety",
            "Sheriff's Office UAS team operating since 2016 for searches, incident response, crash documentation, and law-enforcement support.",
            ("stafford_uas", "dcjs_awards"),
        ),
        (
            "Frederick County Sheriff's Office sUAS Program",
            "program",
            "Winchester",
            "Shenandoah Valley",
            "public_safety",
            "Special Operations small-UAS program supporting search and rescue, crash and crime-scene documentation, and public safety.",
            "frederick_uas",
        ),
        (
            "Powhatan County Emergency Management UAS Program",
            "program",
            "Powhatan",
            "Greater Richmond",
            "public_safety",
            "County emergency-management UAS program listed as an active specialty plan with dedicated equipment procedures.",
            "powhatan_uas",
        ),
        (
            "Chesapeake Police UAS Team",
            "program",
            "Chesapeake",
            "Hampton Roads",
            "public_safety",
            "Police Special Operations UAS team supporting city law-enforcement and public-safety response.",
            "chesapeake_uas",
        ),
        (
            "Newport News Drones as First Responders Program",
            "program",
            "Newport News",
            "Hampton Roads",
            "public_safety",
            "City incident-based DFR program integrating police, fire, and EMS with logged flights and public oversight controls.",
            "newport_news_dfr",
        ),
        (
            "ODU Institute for Autonomous and Connected Systems",
            "organization",
            "Norfolk",
            "Hampton Roads",
            "research_cross",
            "Interdisciplinary institute researching uncrewed aerial, surface, and underwater vehicles, robotics, connected mobility, sensing, and AI.",
            "odu_iacs",
        ),
        (
            "ODU Uncrewed Systems Design and Development Minor",
            "program",
            "Norfolk",
            "Hampton Roads",
            "workforce_robotics",
            "Twelve-credit undergraduate minor covering design and operation of uncrewed aerial, surface, and underwater systems.",
            "odu_minor",
        ),
        (
            "ODU Drone Certificate Program",
            "program",
            "Norfolk",
            "Hampton Roads",
            "workforce",
            "Hands-on certificate program identified by ODU's autonomy institute as preparation for engineers, scientists, and drone innovators.",
            "odu_iacs",
        ),
        (
            "ODU Maritime Autonomous Systems Test Site",
            "facility",
            "Norfolk",
            "Hampton Roads",
            "research_marine",
            "Willoughby Bay waterfront test site with a floating dock, crane, covered workspace, utilities, and chase boat for autonomous surface and underwater systems.",
            "odu_masts",
        ),
        (
            "VIMS Collaboratory for Physical Oceanography",
            "organization",
            "Williamsburg",
            "Hampton Roads",
            "research_marine",
            "Marine research group using autonomous underwater gliders, floats, drifters, radar, satellites, moorings, and ships for coastal observations.",
            "vims_c4po",
        ),
        (
            "VIMS Autonomous Systems Laboratory",
            "organization",
            "Williamsburg",
            "Hampton Roads",
            "research_marine",
            "Laboratory designing and building free-swimming autonomous underwater vehicles for oceanographic sensing and field research.",
            "vims_asl",
        ),
        (
            "VIMS Harmful Algal Bloom Drone Monitoring",
            "program",
            "Williamsburg",
            "Hampton Roads",
            "agriculture",
            "Aerial-drone monitoring program capturing high-definition imagery to locate and track harmful algal blooms in the lower Chesapeake Bay.",
            "vims_hab",
        ),
        (
            "Blue Vigil",
            "organization",
            "Sterling",
            "Northern Virginia",
            "company_air",
            "Virginia company developing tethered-drone power systems and autonomous aerial lighting for construction, public safety, utilities, and emergency scenes.",
            ("blue_vigil", "vedp_keltech"),
        ),
        (
            "P1 Technologies Keltech Division",
            "organization",
            "Roanoke",
            "Roanoke Valley",
            "enabling",
            "Roanoke manufacturing operation documented by VEDP as the producer of Blue Vigil's tethered-drone systems.",
            ("p1_technologies", "vedp_keltech"),
        ),
        (
            "Virginia Smart Community Testbed",
            "operating-environment",
            "Stafford",
            "Fredericksburg Region",
            "test_multi",
            "Stafford living laboratory for emerging technologies with a documented 5G public-safety drone pilot and autonomous-equipment demonstrations.",
            "smart_testbed",
        ),
        (
            "Virginia Spaceport Authority",
            "organization",
            "Norfolk",
            "Hampton Roads",
            "state",
            "State authority that owns and operates MARS and its dedicated UAS airfield, restricted-airspace access, runway, VTOL pad, and hangar.",
            "space_authority",
        ),
    ]
)

# Facilities and operating organizations added in the August 2026 statewide expansion.
# Each entry is distinct from its parent campus, installation, or countywide program.
CURATED_ASSETS.extend(
    [
        (
            "NASA Langley ROAM UAS Operations Center",
            "facility",
            "Hampton",
            "Hampton Roads",
            "research_air",
            "Building 1268 operations center for BVLOS research, live-virtual-constructive flight operations, and human-autonomy teaming with multiple vehicles.",
            "nasa_roam",
        ),
        (
            "NASA Langley UAS Test Range",
            "operating-environment",
            "Hampton",
            "Hampton Roads",
            "research_air",
            "NASA-operated 100-acre small-UAS flight range supporting research flights and testing near the CERTAIN city environment.",
            "nasa_certain",
        ),
        (
            "Wallops Research Park",
            "operating-environment",
            "Wallops Island",
            "Eastern Shore",
            "test_multi",
            "Publicly documented aerospace and science research park adjoining NASA Wallops, with land planned for research, education, aircraft, and industrial activity.",
            ("wallops_research_park", "wallops_research_park_location"),
        ),
        (
            "NSWC Dahlgren UAV Test Runway",
            "operating-environment",
            "Dahlgren",
            "Fredericksburg Region",
            "federal_autonomy",
            "Dedicated Navy runway identified for in-house research, development, and testing of UAV sensors, payloads, and weapons.",
            "nswc_dahlgren",
        ),
        (
            "NSWCDD Dam Neck Activity",
            "organization",
            "Virginia Beach",
            "Hampton Roads",
            "federal_autonomy",
            "Dahlgren Division activity developing warfare-system capabilities that include intelligent automation, autonomy, AI, and unmanned systems.",
            "dam_neck_activity",
        ),
        (
            "Navy TALSA East Small UAS Training Facility",
            "facility",
            "Virginia Beach",
            "Hampton Roads",
            "federal_training_air",
            "Navy training and logistics facility providing entry-level small-UAS qualification, system storage, supply, and maintenance support.",
            "talsa_east",
        ),
        (
            "Marine Corps Counter-Drone Team",
            "organization",
            "Quantico",
            "Fredericksburg Region",
            "federal_counter_uas",
            "Weapons Training Battalion element responsible for counter-drone training development, integration, and support to Marine Corps units.",
            "marine_counter_drone_team",
        ),
        (
            "Fairfax County Police Drone as First Responder Program",
            "program",
            "Fairfax",
            "Northern Virginia",
            "public_safety",
            "Operational DFR program using remotely piloted docking-station aircraft and Real Time Crime Center staff for rapid incident awareness.",
            ("fairfax_dfr", "fairfax_county_uas"),
        ),
        (
            "Charles City County Sheriff's Office Drone Operations Team",
            "program",
            "Charles City",
            "Greater Richmond",
            "public_safety",
            "Joint sheriff and fire-EMS drone team formed for search and rescue, disaster response, scene analysis, and emergency operations.",
            "charles_city_uas",
        ),
        (
            "Bedford Fire Department UAS Program",
            "program",
            "Bedford",
            "Lynchburg Region",
            "public_safety",
            "Municipal fire-department drone capability documented through program reporting and a later aircraft-replacement authorization.",
            ("bedford_fire_uas", "bedford_fire_drone_replacement"),
        ),
        (
            "Radford University First Responder UAS Capability",
            "program",
            "Radford",
            "New River Valley",
            "public_safety",
            "A CY 2026 Virginia award documents an unmanned aircraft already used by an eligible university first-responder agency; the public chart does not identify the operator.",
            ("dcjs_awards", "dcjs_drone"),
        ),
        (
            "MAG Aerospace",
            "organization",
            "Fairfax",
            "Northern Virginia",
            "company_cross",
            "Virginia-headquartered aerospace company operating and integrating manned and unmanned aircraft, sensors, and mission systems worldwide.",
            "mag_aerospace",
        ),
        (
            "Inertial Labs",
            "organization",
            "Paeonian Springs",
            "Northern Virginia",
            "enabling",
            "Virginia headquarters and R&D operation developing inertial navigation, positioning, and sensor-fusion systems for UAV, UGV, and marine platforms.",
            "inertial_labs",
        ),
        (
            "DZYNE Technologies",
            "organization",
            "Fairfax",
            "Northern Virginia",
            "company_counter_uas",
            "Fairfax office of an autonomous-systems company developing long-endurance unmanned aircraft, autonomy software, and counter-unmanned capabilities.",
            ("dzyne", "dzyne_location"),
        ),
        (
            "ENSCO",
            "organization",
            "Vienna",
            "Northern Virginia",
            "company_cross",
            "Virginia-headquartered engineering company providing autonomous-system, machine-vision, vehicle-monitoring, and resilient positioning capabilities.",
            ("ensco", "ensco_location"),
        ),
        (
            "Scout Space",
            "organization",
            "Reston",
            "Northern Virginia",
            "company_cross",
            "Reston space-technology company developing autonomous sensing and navigation software for spacecraft inspection and space-domain awareness.",
            ("scout_space", "scout_space_location"),
        ),
        (
            "Universal Solutions International",
            "organization",
            "Newport News",
            "Hampton Roads",
            "company_air",
            "Newport News engineering and professional-services company supporting Army aviation and manned and unmanned aircraft systems.",
            "usi",
        ),
        (
            "Leidos",
            "organization",
            "Reston",
            "Northern Virginia",
            "company_cross",
            "Reston-headquartered technology company with documented multi-domain autonomy, autonomous aerial logistics, maritime autonomy, and uncrewed-systems work.",
            ("leidos_autonomy", "leidos_location"),
        ),
        (
            "CACI International",
            "organization",
            "Reston",
            "Northern Virginia",
            "company_counter_uas",
            "Reston-headquartered defense-technology company providing counter-UAS sensing, electronic warfare, command-and-control, and systems integration.",
            "caci_counter_uas",
        ),
        (
            "Parsons",
            "organization",
            "Chantilly",
            "Northern Virginia",
            "company_counter_uas",
            "Chantilly-headquartered technology company with documented counter-UAS detection, tracking, command-and-control, and defeat solutions.",
            ("parsons_counter_uas", "parsons_location"),
        ),
        (
            "Eagle Aviation Technologies",
            "organization",
            "Newport News",
            "Hampton Roads",
            "company_air",
            "Newport News aerospace design, manufacturing, and test company supporting manned and unmanned platforms and prototype aircraft systems.",
            "eagle_aviation",
        ),
        (
            "Newport News AirCommerce Park",
            "infrastructure",
            "Newport News",
            "Hampton Roads",
            "aviation_site",
            "Airport-property business park with corporate hangars, specialized military training facilities, and development capacity for aviation and UAS activity.",
            ("aircommerce_park", "aircommerce_uas"),
        ),
    ]
)

DCJS_JURISDICTION_UAS_ASSETS = [
    ("Amherst County", "Amherst", "Lynchburg Region"),
    ("Town of Ashland", "Ashland", "Greater Richmond"),
    ("Bath County", "Warm Springs", "Shenandoah Valley"),
    ("Buchanan County", "Grundy", "Southwest Virginia"),
    ("Town of Chilhowie", "Chilhowie", "Southwest Virginia"),
    ("Town of Chincoteague", "Chincoteague", "Eastern Shore"),
    ("Town of Haymarket", "Haymarket", "Northern Virginia"),
    ("Madison County", "Madison", "Central Virginia"),
    ("City of Manassas", "Manassas", "Northern Virginia"),
    ("Town of New Market", "New Market", "Shenandoah Valley"),
    ("Town of Occoquan", "Occoquan", "Northern Virginia"),
    ("Pittsylvania County", "Chatham", "Southside Virginia"),
    ("City of Radford", "Radford", "New River Valley"),
    ("Town of Rocky Mount", "Rocky Mount", "Roanoke Valley"),
    ("Town of Scottsville", "Scottsville", "Central Virginia"),
    ("Smyth County", "Marion", "Southwest Virginia"),
    ("Southampton County", "Courtland", "Southside Virginia"),
    ("City of Staunton", "Staunton", "Shenandoah Valley"),
    ("Wise County", "Wise", "Southwest Virginia"),
    ("Wythe County", "Wytheville", "Southwest Virginia"),
]

CURATED_ASSETS.extend(
    (
        f"{jurisdiction} First Responder UAS Capability",
        "program",
        place,
        region,
        "public_safety",
        (
            f"A CY 2026 Virginia DCJS award documents an unmanned aircraft already in use by "
            f"an eligible local first responder agency in {jurisdiction}; the public award "
            "record does not identify the operating department."
        ),
        ("dcjs_awards", "dcjs_drone"),
    )
    for jurisdiction, place, region in DCJS_JURISDICTION_UAS_ASSETS
)

CURATED_ASSETS.extend(
    [
        (
            "MITRE National Range",
            "operating-environment",
            "Orange",
            "Central Virginia",
            "national_range",
            "Controlled Orange County proving ground for UAS, counter-UAS, ground robotics, communications, prototyping, and independent evaluation.",
            "mitre_range",
        ),
        (
            "Virginia Economic Development Partnership",
            "organization",
            "Richmond",
            "Greater Richmond",
            "economic_development",
            "Commonwealth economic-development authority providing business attraction, site selection, incentives, talent, and industry support for unmanned systems.",
            ("vedp", "vedp_contact"),
        ),
        (
            "Hampton Roads Alliance",
            "organization",
            "Norfolk",
            "Hampton Roads",
            "economic_development",
            "Regional economic-development organization supporting business attraction, intelligence, site solutions, and autonomous-systems opportunities in Hampton Roads.",
            "hampton_roads_alliance",
        ),
        (
            "GO Virginia",
            "program",
            "Richmond",
            "Greater Richmond",
            "economic_development",
            "Statewide economic-development initiative funding collaborative regional projects involving industry, higher education, local government, and workforce partners.",
            "go_virginia",
        ),
        (
            "Shenandoah Valley Aviation Technology Park",
            "infrastructure",
            "Weyers Cave",
            "Shenandoah Valley",
            "aviation_site",
            "Aviation business and technology site at Shenandoah Valley Regional Airport with completed hangars and publicly documented expansion infrastructure.",
            ("shd_tech_park", "shd_tech_park_site"),
        ),
        (
            "Stafford Regional Airport AAM Integration Project Site",
            "operating-environment",
            "Fredericksburg",
            "Fredericksburg Region",
            "aam_test",
            "Stafford Regional Airport site within the Stafford-Warrenton-Winchester project for integrating drone operations into the National Airspace System.",
            ("doav_aam", "stafford_aam"),
        ),
    ]
)

CATALOG_RELATIONSHIPS = [
    ("Mid-Atlantic Aviation Partnership", "operates", "Virginia Tech Drone Park"),
    ("Mid-Atlantic Aviation Partnership", "operates", "MARS Unmanned Aircraft Systems Airfield"),
    ("Mid-Atlantic Aviation Partnership", "supports", "FAA BEYOND Virginia Team"),
    (
        "Mid-Atlantic Aviation Partnership",
        "supports",
        "Virginia Tech Counter UAS Research and Testing Center",
    ),
    ("Virginia Tech Autonomy and Robotics", "supports", "Virginia Tech Drone Park"),
    (
        "Virginia Tech Autonomy and Robotics",
        "supports",
        "Virginia Tech Center for Marine Autonomy and Robotics",
    ),
    (
        "Virginia Tech Autonomy and Robotics",
        "supports",
        "Virginia Tech Uncrewed Systems Laboratory",
    ),
    (
        "Virginia Tech Center for Marine Autonomy and Robotics",
        "supports",
        "AutoBoat at Virginia Tech",
    ),
    (
        "Virginia Innovation Partnership Corporation",
        "supports",
        "Virginia Unmanned Systems Center",
    ),
    (
        "Virginia Innovation Partnership Corporation",
        "supports",
        "Virginia Public Safety Innovation Center",
    ),
    (
        "Virginia Unmanned Systems Center",
        "supports",
        "Virginia Advanced Air Mobility Program",
    ),
    (
        "Virginia Unmanned Systems Center",
        "supports",
        "Virginia Advanced Air Mobility Alliance",
    ),
    (
        "Virginia Department of Aviation",
        "supports",
        "Virginia Advanced Air Mobility Program",
    ),
    (
        "Virginia Department of Aviation",
        "supports",
        "Virginia Flight Information Exchange",
    ),
    (
        "Virginia Department of Aviation",
        "supports",
        "Stafford Regional Airport AAM Integration Project Site",
    ),
    (
        "Washington Exec/Stafford Rgnl",
        "supports",
        "Stafford Regional Airport AAM Integration Project Site",
    ),
    (
        "Shenandoah Valley Rgnl",
        "operates",
        "Shenandoah Valley Aviation Technology Park",
    ),
    (
        "GO Virginia",
        "supports",
        "Shenandoah Valley Aviation Technology Park",
    ),
    ("The Port of Virginia", "operates", "Norfolk International Terminals"),
    ("The Port of Virginia", "operates", "Virginia International Gateway"),
    ("The Port of Virginia", "operates", "Portsmouth Marine Terminal"),
    ("The Port of Virginia", "operates", "Newport News Marine Terminal"),
    ("The Port of Virginia", "operates", "Richmond Marine Terminal"),
    ("The Port of Virginia", "operates", "Virginia Inland Port"),
    ("The Port of Virginia", "operates", "Craney Island Marine Terminal Project"),
    (
        "Virginia Space Grant Consortium Drone Academies",
        "partners-with",
        "Virginia Peninsula Community College Drone Flight Technician Certificate",
    ),
    (
        "Virginia Space Grant Consortium Drone Academies",
        "partners-with",
        "Tidewater Community College Unmanned Systems Courses",
    ),
    (
        "Virginia Community College System Unmanned Systems Curriculum",
        "supports",
        "Blue Ridge Community College Unmanned Systems Courses",
    ),
    (
        "Virginia Community College System Unmanned Systems Curriculum",
        "supports",
        "Danville Community College Unmanned Systems Courses",
    ),
    (
        "Virginia Community College System Unmanned Systems Curriculum",
        "supports",
        "Eastern Shore Community College Unmanned Systems Courses",
    ),
    (
        "Old Dominion University UAS Operations Program",
        "supports",
        "ODU Unmanned and Autonomous Vehicle Laboratory",
    ),
    (
        "University of Virginia UAS Operations Program",
        "supports",
        "UVA Robotics and Autonomous Systems Research",
    ),
    (
        "Virginia Commonwealth University UAS Operations Program",
        "supports",
        "VCU Autonomous Robots and Vehicles Laboratory",
    ),
    ("NASA Langley Research Center", "supports", "NASA Langley Autonomy Incubator"),
    ("NASA Wallops Flight Facility", "supports", "Mid-Atlantic Regional Spaceport"),
    (
        "Institute for Advanced Learning and Research",
        "supports",
        "IALR AgBOT Precision Agriculture Program",
    ),
    (
        "Institute for Advanced Learning and Research",
        "supports",
        "GO TEC Automation and Robotics Talent Pathway",
    ),
    (
        "Commonwealth Center for Advanced Logistics Systems",
        "operates",
        "Energy-Centric UAS Center for Critical Infrastructure",
    ),
    (
        "Energy-Centric UAS Center for Critical Infrastructure",
        "located-at",
        "Richard Bland College",
    ),
    (
        "Energy-Centric UAS Center for Critical Infrastructure",
        "supports",
        "Tri Cities Exec/Dinwiddie County",
    ),
    (
        "Energy-Centric UAS Center for Critical Infrastructure",
        "supports",
        "Danville Rgnl",
    ),
    (
        "Energy-Centric UAS Center for Critical Infrastructure",
        "supports",
        "Lonesome Pine",
    ),
    (
        "Naval Surface Warfare Center Dahlgren Division",
        "operates",
        "NSWC Dahlgren Outdoor Autonomy Laboratory",
    ),
    (
        "Naval Support Facility Dahlgren",
        "supports",
        "Naval Surface Warfare Center Dahlgren Division",
    ),
    (
        "Joint Expeditionary Base Little Creek-Fort Story",
        "supports",
        "NSWC Carderock Combatant Craft Division",
    ),
    (
        "Marine Corps Base Quantico",
        "supports",
        "Marine Corps Warfighting Laboratory",
    ),
    (
        "NASA Langley Research Center",
        "operates",
        "NASA Langley ROAM UAS Operations Center",
    ),
    (
        "NASA Langley Research Center",
        "operates",
        "NASA Langley UAS Test Range",
    ),
    (
        "NASA Langley ROAM UAS Operations Center",
        "supports",
        "NASA Langley CERTAIN",
    ),
    ("NASA Wallops Flight Facility", "partners-with", "Wallops Research Park"),
    (
        "Naval Surface Warfare Center Dahlgren Division",
        "operates",
        "NSWC Dahlgren UAV Test Runway",
    ),
    ("Dam Neck Annex", "hosts", "NSWCDD Dam Neck Activity"),
    (
        "Joint Expeditionary Base Little Creek-Fort Story",
        "hosts",
        "Navy TALSA East Small UAS Training Facility",
    ),
    ("Marine Corps Base Quantico", "hosts", "Marine Corps Counter-Drone Team"),
    (
        "Fairfax County Unmanned Aircraft Systems Program",
        "supports",
        "Fairfax County Police Drone as First Responder Program",
    ),
    (
        "Radford University",
        "supports",
        "Radford University First Responder UAS Capability",
    ),
    (
        "Newport News AirCommerce Park",
        "located-at",
        "Newport News/Williamsburg Intl",
    ),
]

CATALOG_RELATIONSHIPS.extend(
    [
        (
            "ODU Institute for Autonomous and Connected Systems",
            "supports",
            "ODU Uncrewed Systems Design and Development Minor",
        ),
        (
            "ODU Institute for Autonomous and Connected Systems",
            "supports",
            "ODU Drone Certificate Program",
        ),
        (
            "ODU Institute for Autonomous and Connected Systems",
            "supports",
            "ODU Maritime Autonomous Systems Test Site",
        ),
        (
            "Virginia Institute of Marine Science",
            "supports",
            "VIMS Collaboratory for Physical Oceanography",
        ),
        (
            "Virginia Institute of Marine Science",
            "supports",
            "VIMS Autonomous Systems Laboratory",
        ),
        (
            "Virginia Institute of Marine Science",
            "supports",
            "VIMS Harmful Algal Bloom Drone Monitoring",
        ),
        ("Virginia Spaceport Authority", "operates", "Mid-Atlantic Regional Spaceport"),
        (
            "Virginia Spaceport Authority",
            "operates",
            "MARS Unmanned Aircraft Systems Airfield",
        ),
        ("P1 Technologies Keltech Division", "manufactures-for", "Blue Vigil"),
        (
            "Virginia Innovation Partnership Corporation",
            "supports",
            "Virginia Smart Community Testbed",
        ),
        (
            "Newport News Police and Fire Drone Unit",
            "supports",
            "Newport News Drones as First Responders Program",
        ),
    ]
)


def source(key):
    title, url = SOURCES[key]
    return {"title": title, "url": url}


def sentence(value):
    value = value.strip()
    return value if value.endswith((".", "!", "?")) else f"{value}."


def natural_list(values, limit=3):
    values = list(values[:limit])
    if not values:
        return ""
    if len(values) == 1:
        return values[0]
    if len(values) == 2:
        return f"{values[0]} and {values[1]}"
    return f"{', '.join(values[:-1])}, and {values[-1]}"


def contact_scope(record):
    if record["provenance"] == "virginia-military-factbook":
        return "Installation or agency public information"
    return {
        "university": "Institution general information and admissions",
        "organization": "Organization public information and inquiries",
        "facility": "Facility or operator public information",
        "program": "Program or parent-organization inquiries",
        "infrastructure": "Facility or operator public information",
        "operating-environment": "Site operator or program information",
    }[record["record_type"]]


def contact_source_score(item):
    value = f"{item['title']} {item['url']}".lower()
    score = 0
    if "contact information" in value or "contact-us" in value or "/contact" in value:
        score += 6
    if "phone directory" in value or "directory.aspx" in value:
        score += 5
    if "directory" in value or "locations" in value or "about-us" in value:
        score += 3
    if value.endswith(".pdf"):
        score -= 4
    return score


def default_overview(record):
    record_type = record["record_type"].replace("-", " ")
    capabilities = natural_list(record.get("capabilities", []))
    missions = natural_list(record.get("missions", []), limit=2)
    details = [
        f"{sentence(record['short_description'])} Public sources support its classification "
        f"as a Virginia {record_type}."
    ]
    if capabilities:
        details.append(f"Documented capabilities include {capabilities}.")
    if missions:
        details.append(f"Relevant mission areas include {missions}.")
    return " ".join(details)


def finalize_record(record):
    record.update(ASSET_DETAIL_ENRICHMENT.get(record["name"], {}))
    record.setdefault("overview", default_overview(record))
    record.setdefault("contact_phone", "")
    record.setdefault("contact_email", "")

    if not record.get("contact_url"):
        ranked_sources = sorted(
            record["sources"], key=contact_source_score, reverse=True
        )
        best_source = ranked_sources[0]
        record["contact_url"] = best_source["url"]
        if contact_source_score(best_source) > 0:
            record.setdefault("contact_text", contact_scope(record))
        else:
            record.setdefault(
                "contact_text",
                "Public information route; a direct asset contact is not published in the catalog",
            )
    else:
        record.setdefault("contact_text", contact_scope(record))

    contact_override = CONTACT_ENRICHMENT.get(record["name"])
    if contact_override:
        for field in ("contact_phone", "contact_email", "contact_url"):
            if contact_override.get(field):
                record[field] = contact_override[field]
        record["contact_text"] = contact_scope(record)
        source_url = contact_override["source_url"]
        if not any(item["url"] == source_url for item in record["sources"]):
            record["sources"].append(
                {
                    "title": f"{record['name']} public contact information",
                    "url": source_url,
                }
            )

    if not any(item["url"] == record["contact_url"] for item in record["sources"]):
        record["sources"].append(
            {
                "title": f"{record['name']} public contact information",
                "url": record["contact_url"],
            }
        )
    return record


def apply_location_override(record):
    override = LOCATION_OVERRIDES.get(record["name"])
    if not override:
        return record

    for field in (
        "address_line",
        "city",
        "postal_code",
        "latitude",
        "longitude",
        "location_precision",
    ):
        if field in override:
            record[field] = override[field]
    record["location_precision"] = override.get("location_precision", "site")

    location_source = override.get("source")
    if location_source:
        title, url = location_source
        if not any(item["url"] == url for item in record["sources"]):
            record["sources"].append({"title": title, "url": url})
    return record


def point_in_ring(longitude, latitude, ring):
    inside = False
    previous_x, previous_y = ring[-1]
    for current_x, current_y in ring:
        if (current_y > latitude) != (previous_y > latitude):
            boundary_x = (previous_x - current_x) * (latitude - current_y) / (
                previous_y - current_y
            ) + current_x
            if longitude < boundary_x:
                inside = not inside
        previous_x, previous_y = current_x, current_y
    return inside


def point_in_geometry(longitude, latitude, geometry):
    polygons = (
        [geometry["coordinates"]]
        if geometry["type"] == "Polygon"
        else geometry["coordinates"]
    )
    return any(
        point_in_ring(longitude, latitude, polygon[0])
        and not any(point_in_ring(longitude, latitude, hole) for hole in polygon[1:])
        for polygon in polygons
    )


def region_for(latitude, longitude):
    for feature in REGION_FEATURES:
        if point_in_geometry(longitude, latitude, feature["geometry"]):
            return feature["properties"]["region_name"]

    if longitude > -75.55:
        return "Eastern Shore"
    if latitude > 38.45 and longitude > -78.35:
        return "Northern Virginia"
    if longitude < -81.0:
        return "Southwest Virginia"
    if latitude < 37.25 and longitude < -79.55:
        return "New River Valley"
    if latitude < 37.35 and longitude < -77.0:
        return "Southside Virginia"
    if longitude < -79.3 and latitude < 38.0:
        return "Roanoke Valley"
    if longitude < -78.15 and latitude > 37.65:
        return "Shenandoah Valley"
    if longitude > -77.15 and latitude < 37.55:
        return "Hampton Roads"
    if -77.9 < longitude < -76.8 and 37.2 < latitude < 38.15:
        return "Greater Richmond"
    return "Central Virginia"


class AirportSponsorTableParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self.current_row = None
        self.current_cell = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.current_row = []
        elif tag == "td" and self.current_row is not None:
            self.current_cell = []

    def handle_data(self, data):
        if self.current_cell is not None:
            self.current_cell.append(data)

    def handle_endtag(self, tag):
        if tag == "td" and self.current_cell is not None:
            self.current_row.append(" ".join("".join(self.current_cell).split()))
            self.current_cell = None
        elif tag == "tr" and self.current_row is not None:
            if len(self.current_row) >= 23:
                self.rows.append(self.current_row)
            self.current_row = None


def format_phone(value):
    digits = "".join(character for character in value if character.isdigit())
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) < 10:
        return value.strip()
    phone = f"{digits[:3]}-{digits[3:6]}-{digits[6:10]}"
    return f"{phone} ext. {digits[10:]}" if len(digits) > 10 else phone


def normalize_airport_postal_code(value):
    digits = "".join(character for character in value if character.isdigit())
    return digits[:5]


def fetch_airport_sponsor_contacts():
    request = urllib.request.Request(
        DOAV_SPONSOR_DIRECTORY,
        headers={"User-Agent": "cosolve-uxs-map-catalog/1.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        page = response.read().decode("utf-8", errors="replace")
    parser = AirportSponsorTableParser()
    parser.feed(page)

    contacts = {}
    for cells in parser.rows:
        identifier = cells[0].strip()
        manager_name, manager_email, manager_phone = cells[19:22]
        sponsor_name, sponsor_contact, sponsor_email, sponsor_phone = cells[14:18]
        contact_name = manager_name or sponsor_contact or sponsor_name
        contacts[identifier] = {
            "name": contact_name,
            "email": manager_email or sponsor_email,
            "phone": manager_phone or sponsor_phone,
            "role": cells[2],
            "address_line": cells[3],
            "city": cells[4],
            "postal_code": normalize_airport_postal_code(cells[5]),
        }
    return contacts


def fetch_public_airports():
    params = urllib.parse.urlencode(
        {
            "where": "STATE='VA' AND PRIVATEUSE=0 AND OPERSTATUS='OPERATIONAL' AND TYPE_CODE IN ('AD','SP')",
            "outFields": "IDENT,NAME,SERVCITY,TYPE_CODE",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "geojson",
        }
    )
    request = urllib.request.Request(
        f"{FAA_LAYER}/query?{params}", headers={"User-Agent": "cosolve-uxs-map-catalog/1.0"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        return json.load(response)["features"]


def airport_records():
    records = []
    sponsor_contacts = fetch_airport_sponsor_contacts()
    faa_source = {
        "title": "FAA Airports Feature Service",
        "url": FAA_LAYER,
    }
    doav_source = {
        "title": "Virginia Public-use Airport Directory",
        "url": DOAV_DIRECTORY,
    }
    sponsor_source = {
        "title": "Virginia Airport Sponsor and Manager Directory",
        "url": DOAV_SPONSOR_DIRECTORY,
    }
    for feature in fetch_public_airports():
        properties = feature["properties"]
        longitude, latitude = feature["geometry"]["coordinates"][:2]
        name = properties["NAME"].strip()
        city = properties["SERVCITY"].replace("/", " / ").title()
        identifier = properties["IDENT"]
        contact = sponsor_contacts.get(
            identifier,
            {
                "name": "",
                "email": "",
                "phone": "804-236-3624",
                "role": "public-use aviation facility",
                "address_line": "",
                "city": city,
                "postal_code": "",
            },
        )
        airport_kind = "seaplane base" if properties["TYPE_CODE"] == "SP" else "airport"
        contact_name = contact["name"]
        records.append(
            {
                "name": name,
                "record_type": "infrastructure",
                "short_description": (
                    f"Operational public-use {airport_kind} in {contact['city'] or city} "
                    f"(FAA identifier {identifier})."
                ),
                "overview": (
                    f"{name} is an operational public-use {airport_kind} listed by the FAA under "
                    f"identifier {identifier}. The Virginia airport sponsor directory classifies "
                    f"the facility as {contact['role']}."
                ),
                "unmanned_systems_relevance": (
                    f"{name} is included as public aviation infrastructure serving {city}. "
                    "Its inclusion does not imply authorization for unmanned-aircraft operations; "
                    "airport, operator, and airspace approvals still apply."
                ),
                "address_line": contact["address_line"],
                "city": contact["city"] or city,
                "state": "VA",
                "postal_code": contact["postal_code"],
                "latitude": round(latitude, 6),
                "longitude": round(longitude, 6),
                "location_precision": "exact",
                "region": AIRPORT_REGION_OVERRIDES.get(identifier, region_for(latitude, longitude)),
                "strategic_categories": ["Physical infrastructure and logistics"],
                "platform_domains": ["Unmanned aircraft systems"],
                "capabilities": ["Operations, maintenance, and sustainment"],
                "missions": [],
                "website_url": DOAV_DIRECTORY,
                "contact_text": (
                    f"Airport public contact: {contact_name}"
                    if contact_name
                    else "Virginia Department of Aviation public information"
                ),
                "contact_phone": format_phone(contact["phone"]),
                "contact_email": contact["email"],
                "contact_url": DOAV_SPONSOR_DIRECTORY,
                "sources": [faa_source, doav_source, sponsor_source],
                "provenance": "faa-public-airport",
            }
        )
    return records


def defense_records():
    records = []
    factbook_source = {
        "title": "Virginia Military Factbook",
        "url": FACTBOOK,
    }
    for name, place, region in DEFENSE_INSTALLATIONS:
        latitude, longitude = PLACES[place]
        records.append(
            apply_location_override(
                {
                    "name": name,
                    "record_type": "organization",
                    "short_description": (
                        f"{name}, a publicly documented military or federal installation in {place}."
                    ),
                    "unmanned_systems_relevance": (
                        f"{name} is included as documented federal or defense ecosystem presence in "
                        f"{place}. Its map point is generalized and omits operational detail."
                    ),
                    "city": place,
                    "state": "VA",
                    "latitude": latitude,
                    "longitude": longitude,
                    "location_precision": "locality",
                    "region": region,
                    "strategic_categories": ["Federal and defense customer access"],
                    "platform_domains": ["Cross-domain autonomy"],
                    "capabilities": ["Systems engineering and integration"],
                    "missions": ["Force protection and installation security"],
                    "website_url": FACTBOOK,
                    "sources": [factbook_source],
                    "provenance": "virginia-military-factbook",
                }
            )
        )
    return records


def normalize_public_url(value):
    value = value.strip()
    if value.startswith("http://"):
        return "https://" + value.removeprefix("http://")
    if value.startswith("https://"):
        return value
    return "https://" + value


def fetch_ipeds_directory():
    request = urllib.request.Request(
        IPEDS_DIRECTORY_ZIP,
        headers={"User-Agent": "cosolve-uxs-map-catalog/1.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        archive_bytes = response.read()
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        csv_name = next(name for name in archive.namelist() if name.lower().endswith(".csv"))
        with archive.open(csv_name) as raw_file:
            text_file = io.TextIOWrapper(raw_file, encoding="utf-8-sig", newline="")
            return list(csv.DictReader(text_file))


def eligible_virginia_institutions():
    institutions = []
    for row in fetch_ipeds_directory():
        if not (
            row["STABBR"] == "VA"
            and row["CYACTIVE"] == "1"
            and row["DEGGRANT"] == "1"
        ):
            continue

        name = IPEDS_NAME_ALIASES.get(row["INSTNM"], row["INSTNM"])
        included_sector = row["CONTROL"] in {"1", "2"} or name == "ECPI University"
        if not included_sector or name == "Eastern Virginia Medical School":
            continue

        row["catalog_name"] = name
        institutions.append(row)
    return institutions


def institution_description(row):
    city = row["CITY"].strip()
    if row["CONTROL"] == "1" and row["ICLEVEL"] == "2":
        return f"Public degree-granting community college based in {city}, Virginia."
    if row["CONTROL"] == "1":
        return f"Public degree-granting college or university based in {city}, Virginia."
    if row["CONTROL"] == "2":
        return (
            f"Private nonprofit degree-granting college or university based in {city}, Virginia."
        )
    return f"Private degree-granting university based in {city}, Virginia."


def university_records():
    detailed_assets = {item[0]: item for item in UNIVERSITY_ASSETS}
    records = []
    for row in eligible_virginia_institutions():
        name = row["catalog_name"]
        detailed_asset = detailed_assets.get(name)
        latitude = round(float(row["LATITUDE"]), 6)
        longitude = round(float(row["LONGITUD"]), 6)
        website_url = normalize_public_url(row["WEBADDR"])
        contact_url = (
            normalize_public_url(row["ADMINURL"])
            if row.get("ADMINURL", "").strip()
            else website_url
        )
        ipeds_source = {
            "title": "NCES IPEDS 2024 institutional directory",
            "url": IPEDS_DIRECTORY_PAGE,
        }
        if detailed_asset:
            _name, _place, _region, description, source_key, _children = detailed_asset
            institution_source = source(source_key)
            relevance = (
                f"{name} is mapped at the institution level to connect its source-backed "
                "unmanned-systems research, education, operations, facilities, and programs."
            )
            categories = ["Research and technical depth", "Workforce and talent"]
            domains = ["Cross-domain autonomy"]
            capabilities = [
                "Autonomy and artificial intelligence",
                "Systems engineering and integration",
            ]
            missions = ["Training and experimentation"]
            provenance = "university-institution"
            overview = (
                f"This institution-level entry connects {name} to its separately documented "
                "research, education, facilities, operations, and programs in the asset catalog."
            )
        else:
            description = institution_description(row)
            institution_source = {
                "title": f"{name} official website",
                "url": website_url,
            }
            relevance = (
                f"{name} is included as statewide higher-education and workforce infrastructure. "
                "Inclusion identifies institutional capacity and does not by itself indicate a "
                "documented unmanned-systems program."
            )
            categories = ["Workforce and talent"]
            domains = []
            capabilities = []
            missions = []
            provenance = "nces-ipeds-higher-education"
            overview = (
                f"{name} is included at the institution level as part of Virginia's education "
                "and workforce infrastructure. The listing does not claim a dedicated unmanned-"
                "systems program unless a separate source-backed program is documented."
            )

        contact_source = {
            "title": f"{name} admissions and public contact information",
            "url": contact_url,
        }
        record_sources = [institution_source, ipeds_source]
        if not any(item["url"] == contact_url for item in record_sources):
            record_sources.append(contact_source)

        records.append(
            apply_location_override(
                {
                    "name": name,
                    "record_type": "university",
                    "short_description": description,
                    "overview": overview,
                    "unmanned_systems_relevance": relevance,
                    "address_line": " ".join(row["ADDR"].split()),
                    "city": row["CITY"].strip(),
                    "state": "VA",
                    "latitude": latitude,
                    "longitude": longitude,
                    "postal_code": row["ZIP"].strip(),
                    "location_precision": "site",
                    "region": region_for(latitude, longitude),
                    "strategic_categories": categories,
                    "platform_domains": domains,
                    "capabilities": capabilities,
                    "missions": missions,
                    "website_url": website_url,
                    "contact_text": "Institution general information and admissions",
                    "contact_phone": format_phone(row.get("GENTELE", "")),
                    "contact_email": "",
                    "contact_url": contact_url,
                    "sources": record_sources,
                    "provenance": provenance,
                }
            )
        )
    return records


def university_relationships():
    return [
        (university_name, "supports", child_name)
        for university_name, _place, _region, _description, _source_key, children in UNIVERSITY_ASSETS
        for child_name in children
    ]


def curated_records():
    records = []
    for name, record_type, place, region, profile_key, description, source_key in CURATED_ASSETS:
        latitude, longitude = PLACES[place]
        profile = PROFILES[profile_key]
        source_keys = (source_key,) if isinstance(source_key, str) else source_key
        record_sources = [source(key) for key in source_keys]
        records.append(
            apply_location_override(
                {
                    "name": name,
                    "record_type": record_type,
                    "short_description": description,
                    "unmanned_systems_relevance": profile["relevance"],
                    "city": place,
                    "state": "VA",
                    "latitude": latitude,
                    "longitude": longitude,
                    "location_precision": "locality",
                    "region": region,
                    "strategic_categories": profile["categories"],
                    "platform_domains": profile["domains"],
                    "capabilities": profile["capabilities"],
                    "missions": profile["missions"],
                    "website_url": record_sources[0]["url"],
                    "sources": record_sources,
                    "provenance": "curated-public-source",
                }
            )
        )
    return records


def validate(records, relationships):
    names = set()
    for record in records:
        if record["name"] in names:
            raise ValueError(f"Duplicate asset name: {record['name']}")
        names.add(record["name"])
        if not record["sources"] or not all(item.get("url") for item in record["sources"]):
            raise ValueError(f"Missing source URL: {record['name']}")
        if not record.get("overview"):
            raise ValueError(f"Missing asset overview: {record['name']}")
        if not record.get("contact_text") or not record.get("contact_url"):
            raise ValueError(f"Missing public contact route: {record['name']}")
        if not record["contact_url"].startswith("https://"):
            raise ValueError(f"Invalid public contact URL: {record['name']}")
        if not any(item["url"] == record["contact_url"] for item in record["sources"]):
            raise ValueError(f"Contact route is not source-backed: {record['name']}")
        activity_claims = (
            record.get("activity_status"),
            record.get("current_activity"),
            record.get("partnership_opportunities"),
        )
        if any(activity_claims):
            if not record.get("activity_source_url") or not record.get(
                "activity_last_verified_at"
            ):
                raise ValueError(f"Unverified activity details: {record['name']}")
            if not any(
                item["url"] == record["activity_source_url"] for item in record["sources"]
            ):
                raise ValueError(f"Activity source is not attached: {record['name']}")
        development_claims = (
            record.get("owner_operator"),
            record.get("available_acreage"),
            record.get("development_status"),
            record.get("development_notes"),
            record.get("infrastructure_access"),
        )
        if any(value not in (None, "") for value in development_claims):
            if not record.get("development_source_url") or not record.get(
                "development_last_verified_at"
            ):
                raise ValueError(f"Unverified development details: {record['name']}")
            if not any(
                item["url"] == record["development_source_url"]
                for item in record["sources"]
            ):
                raise ValueError(f"Development source is not attached: {record['name']}")
        if record.get("available_acreage", 0) < 0:
            raise ValueError(f"Negative acreage: {record['name']}")
        latitude = record["latitude"]
        longitude = record["longitude"]
        if (latitude is None) != (longitude is None):
            raise ValueError(f"Incomplete coordinates: {record['name']}")
        if latitude is not None and not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise ValueError(f"Invalid coordinates: {record['name']}")
        if record["location_precision"] in {"exact", "site"} and not record.get("address_line"):
            if record["provenance"] != "faa-public-airport":
                raise ValueError(f"Specific location is missing an address: {record['name']}")
        if record["location_precision"] == "regional" and latitude is not None:
            raise ValueError(f"Regional record must not expose a point: {record['name']}")
        if len(record["short_description"]) > 320:
            raise ValueError(f"Description too long: {record['name']}")

    relationship_assets = {
        asset_name
        for relationship in relationships
        for asset_name in (relationship[0], relationship[2])
    }
    unknown_assets = relationship_assets - names
    if unknown_assets:
        raise ValueError(f"Unknown relationship assets: {', '.join(sorted(unknown_assets))}")


def main():
    records = airport_records() + defense_records() + university_records() + curated_records()
    records = [finalize_record(record) for record in records]
    records.sort(key=lambda item: item["name"].casefold())
    relationships = list(CATALOG_RELATIONSHIPS) + university_relationships()
    relationships.extend(
        ("Virginia Department of Aviation", "supports", record["name"])
        for record in records
        if record["provenance"] == "faa-public-airport"
    )
    validate(records, relationships)
    payload = {
        "generated_at": CATALOG_DATE,
        "record_count": len(records),
        "methodology": (
            "Current operational public-use aviation facilities from the FAA feature service, "
            "publicly listed installations from the Virginia Military Factbook, active Virginia "
            "public and private nonprofit degree-granting institutions from the NCES IPEDS 2024 "
            "directory (plus ECPI University), and a curated set of source-backed ecosystem "
            "records. Specific street and site locations are "
            "anchored to official public address sources and geocoded against the U.S. Census "
            "address ranges or named-site map data; locality points are retained when the public "
            "record does not identify the operating department or facility."
        ),
        "relationships": [
            {"from": from_name, "type": relationship_type, "to": to_name}
            for from_name, relationship_type, to_name in relationships
        ],
        "records": records,
    }
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {len(records)} real Virginia assets to {OUTPUT}")


if __name__ == "__main__":
    main()
