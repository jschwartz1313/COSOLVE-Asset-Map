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
CATALOG_DATE = "2026-08-21"
BUILD_DATE = "2026-08-24"

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
WEBSITE_ENRICHMENT_PATH = ROOT / "data" / "asset_website_enrichment.json"
PRIORITY_PROFILE_ENRICHMENT_PATH = ROOT / "data" / "priority_profile_enrichment.json"
SOURCE_ENRICHMENT_PATH = ROOT / "data" / "asset_source_enrichment.json"
LOCATION_ENRICHMENT_PATH = ROOT / "data" / "asset_location_enrichment.json"

IPEDS_NAME_ALIASES = {
    "University of Virginia-Main Campus": "University of Virginia",
    "Virginia Polytechnic Institute and State University": "Virginia Tech",
}
INSTITUTION_CONTACT_OVERRIDES = {
    "Hampden-Sydney College": "https://www.hsc.edu/admission-and-financial-aid/",
}
SPECIALIZED_HIGHER_ED_EXCLUSIONS = {
    "Appalachian College of Pharmacy",
    "Ascent College",
    "Bon Secours Memorial College of Nursing",
    "Bon Secours St Mary's Hospital School of Medical Imaging",
    "Centra College",
    "Divine Mercy University",
    "Edward Via College of Osteopathic Medicine",
    "Riverside College of Health Careers",
    "Sentara College of Health Sciences",
    "Southside College of Health Sciences",
    "Union Presbyterian Seminary",
    "Virginia Beach Theological Seminary",
    "Virginia University of Integrative Medicine",
}
REGION_FEATURES = json.loads(REGION_BOUNDARIES.read_text())["features"]
CONTACT_ENRICHMENT = (
    json.loads(CONTACT_ENRICHMENT_PATH.read_text()).get("assets", {})
    if CONTACT_ENRICHMENT_PATH.exists()
    else {}
)
WEBSITE_ENRICHMENT = (
    json.loads(WEBSITE_ENRICHMENT_PATH.read_text()).get("assets", {})
    if WEBSITE_ENRICHMENT_PATH.exists()
    else {}
)
PRIORITY_PROFILE_ENRICHMENT = (
    json.loads(PRIORITY_PROFILE_ENRICHMENT_PATH.read_text()).get("assets", {})
    if PRIORITY_PROFILE_ENRICHMENT_PATH.exists()
    else {}
)
SOURCE_ENRICHMENT = (
    json.loads(SOURCE_ENRICHMENT_PATH.read_text()).get("assets", {})
    if SOURCE_ENRICHMENT_PATH.exists()
    else {}
)
LOCATION_ENRICHMENT = (
    json.loads(LOCATION_ENRICHMENT_PATH.read_text()).get("assets", {})
    if LOCATION_ENRICHMENT_PATH.exists()
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
    "vipc_contact": (
        "Virginia Innovation Partnership Corporation contact information",
        "https://vipc.org/contact-us/",
    ),
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
    "hii_center_completion": (
        "HII: first Unmanned Systems Center phase completed",
        "https://www.hii.com/news/first-quarter-2021-earnings",
    ),
    "hii_mission_technologies": (
        "HII Mission Technologies uncrewed systems capabilities",
        "https://www.hii.com/mission-technologies",
    ),
    "longbow": (
        "U.S. Small Business Innovation Research portfolio: The Longbow Group",
        "https://www.sbir.gov/portfolio/1664155",
    ),
    "longbow_current": (
        "U.S. Small Business Innovation Research portfolio: The Longbow Group",
        "https://www.sbir.gov/portfolio/1664155",
    ),
    "aac": ("Advanced Aircraft Company", "https://advancedaircraftcompany.com/"),
    "aac_products": (
        "Advanced Aircraft Company UAS products and public contact information",
        "https://advancedaircraftcompany.com/uas-products/",
    ),
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
    "aerovironment_contact": (
        "AeroVironment contact information",
        "https://www.avinc.com/contact/",
    ),
    "aerovironment_partners": (
        "AeroVironment MacCready Works partnerships",
        "https://www.avinc.com/about/maccready-works/",
    ),
    "aurora_contact": (
        "Aurora Flight Sciences contact information",
        "https://www.aurora.aero/contact-us/",
    ),
    "anra_home": (
        "ANRA Technologies airspace and mission management",
        "https://www.anratechnologies.com/home/",
    ),
    "anra_location": (
        "ANRA Technologies Reston location",
        "https://www.anratechnologies.com/home/system-architect/",
    ),
    "anra_current": (
        "ANRA Technologies current airspace-management deployment",
        "https://www.anratechnologies.com/home/2026/06/24/building-michigans-digital-airspace-integrating-commercial-drone-operations-and-airspace-security/",
    ),
    "anra_partnership": (
        "ANRA Technologies airspace-management consultation",
        "https://www.anratechnologies.com/home/airspace-management/",
    ),
    "maap_about": (
        "Mid-Atlantic Aviation Partnership overview",
        "https://maap.ictas.vt.edu/About/about-us.html",
    ),
    "maap_contact": (
        "Mid-Atlantic Aviation Partnership contact information",
        "https://maap.ictas.vt.edu/Contact.html",
    ),
    "maap_beyond": (
        "Virginia FAA BEYOND partnership",
        "https://maap.ictas.vt.edu/BEYOND/aboutBEYOND.html",
    ),
    "vt_drone_park": (
        "Virginia Tech Drone Park facility and scheduling information",
        "https://ictas.vt.edu/Facilities/ictas-drone-park.html",
    ),
    "qinetiq": ("QinetiQ US locations", "https://www.qinetiq.com/en-us/who-we-are/our-locations"),
    "dedrone": ("Dedrone by Axon", "https://www.axon.com/products/dedrone"),
    "dedrone_acquisition": (
        "Axon completes acquisition of Dedrone",
        "https://www.axon.com/blog/axon-completes-acquisition-of-dedrone",
    ),
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
        "Eastern Shore 911 Communications Manual: Accomack County Drone Team",
        "https://www.esva911.org/Communications%20Manual%20-%20Public%20Release%20Version-%20UPDATED%2011-26-24.pdf",
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
    "autonomous_flight_location": (
        "Autonomous Flight Technologies Salem office and employment information",
        "https://www.autonomousflight.us/careers",
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
        "Orange County Sheriff's Office academy curriculum including drone operations",
        "https://www.orangecountyva.gov/DocumentCenter/View/5121/"
        "2026-Citizens-Police-Academy-Overview-and-Application?bidId=",
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
    "amherst_fire_drone": (
        "Amherst County emergency-services minutes documenting the Fire Department drone",
        "https://www.countyofamherst.com/egov/documents/1730910273_75599.pdf",
    ),
    "amherst_fire_equipment": (
        "Amherst County Fire and EMS equipment schedule listing unmanned aircraft",
        "https://www.countyofamherst.com/egov/documents/1749654223_53408.pdf",
    ),
    "amherst_fire_contact": (
        "Amherst County Fire and EMS contact information",
        "https://www.countyofamherst.com/department/index.php?structureid=23",
    ),
    "staunton_police_uas": (
        "Staunton Police Department homeland-security UAS appropriation",
        "https://www.ci.staunton.va.us/Home/Components/MeetingsManager/"
        "MeetingAgenda/ShowPrimaryDocument/?agendaID=1054&includeTrash=False&isPub=True",
    ),
    "staunton_police_contact": (
        "Staunton Police Department contact information",
        "https://www.ci.staunton.va.us/departments/police",
    ),
    "ashland_police_drone": (
        "Ashland Police Department monthly report documenting drone operations",
        "https://www.ashlandva.gov/DocumentCenter/View/6463/July-2024-1?bidId=",
    ),
    "haymarket_police_drone": (
        "Haymarket Town Council packet documenting the implemented drone program",
        "https://www.townofhaymarket.org/sites/default/files/fileattachments/town_council/meeting/11057/tc_regmtg_03_06_2023.pdf",
    ),
    "madison_sheriff_drone": (
        "Madison County FY2026 UAS grant appropriation",
        "https://www.madisonco.virginia.gov/AgendaCenter/ViewFile/Agenda/_02102026-398",
    ),
    "occoquan_police_drone": (
        "Occoquan 2026 public-safety drone replacement grant",
        "https://occoquanva.gov/wp-content/uploads/2026/01/TC-Agenda-Packet-FULL-1-6-2026.pdf",
    ),
    "radford_police_drone": (
        "Radford City Police Department 2026 drone replacement grant",
        "https://www.radfordva.gov/AgendaCenter/ViewFile/Minutes/_01272026-805",
    ),
    "wise_sheriff_drone": (
        "Wise County Sheriff's Office 2026 unmanned-aircraft grant",
        "https://www.wisecounty.org/AgendaCenter/ViewFile/Agenda/_02122026-671",
    ),
    "wythe_sheriff_drone": (
        "Wythe County Sheriff's Office 2026 unmanned-aircraft grant",
        "https://www.wytheco.org/AgendaCenter/ViewFile/Agenda/_01272026-119",
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
    "odu_nsi": (
        "ODU National Security Institute",
        "https://www.odu.edu/national-security",
    ),
    "odu_nsi_facilities": (
        "ODU National Security Institute facilities and test environments",
        "https://www.odu.edu/national-security/facilities-test-environments",
    ),
    "odu_maritime_conference": (
        "ODU 2026 Maritime and Autonomous Systems Conference facility overview",
        "https://www.odu.edu/sites/default/files/2026/documents/maritime-conference.pdf",
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
    "wallops_aerospace": (
        "Accomack County aerospace assets",
        "https://www.accomack.gov/692/Aerospace",
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
    "dzyne_current": (
        "DZYNE current locations and Ondas Sentinel ownership",
        "https://dzyne.com/contact-us/",
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
    "aircommerce_growth": (
        "Newport News EDA aviation manufacturing and site-readiness projects",
        "https://newportnewsva.com/manufacturing-growth/",
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

CORE_ASSET_CATEGORY = "Core unmanned-systems asset"
SUPPORTING_ASSET_CATEGORY = "Supporting ecosystem asset"
SUPPORTING_PROFILE_KEYS = {
    "aviation_site",
    "economic_development",
    "enabling",
    "port",
}


def ecosystem_role_categories(categories, *, core):
    role = CORE_ASSET_CATEGORY if core else SUPPORTING_ASSET_CATEGORY
    return [*categories, role]


ASSET_DETAIL_SOURCE_KEYS = {
    "Advanced Aircraft Company": ("aac_products",),
    "AeroVironment Corporate Headquarters": (
        "aerovironment_contact",
        "aerovironment_partners",
    ),
    "ANRA Technologies": (
        "anra_home",
        "anra_location",
        "anra_current",
        "anra_partnership",
    ),
    "Aurora Flight Sciences": ("aurora_contact",),
    "HII Unmanned Systems Center of Excellence": (
        "hii_center_completion",
        "hii_mission_technologies",
    ),
    "Longbow Unmanned Systems Research and Test Center": ("longbow_current",),
    "Former Dedrone Washington-Area Headquarters": ("dedrone_acquisition",),
    "Autonomous Flight Technologies": ("autonomous_flight_location",),
    "DZYNE Technologies": ("dzyne_current",),
    "Mid-Atlantic Aviation Partnership": ("maap_about", "maap_contact", "maap_beyond"),
    "Newport News AirCommerce Park": ("aircommerce_growth",),
    "ODU Institute for Autonomous and Connected Systems": ("odu_nsi",),
    "ODU Maritime Autonomous Systems Test Site": (
        "odu_nsi",
        "odu_nsi_facilities",
        "odu_maritime_conference",
    ),
    "Virginia Tech Drone Park": ("vt_drone_park",),
    "Virginia Unmanned Systems Center": ("vipc_contact",),
    "Wallops Research Park": ("wallops_aerospace",),
}

ASSET_DETAIL_ENRICHMENT = {
    "Virginia Unmanned Systems Center": {
        "activity_status": "active",
        "current_activity": (
            "VIPC operates the center as a statewide nexus for uncrewed systems across land, "
            "air, sea, and space, with public resources, studies, grants, partnerships, and "
            "advanced-air-mobility coordination."
        ),
        "partnership_opportunities": (
            "Organizations can use VIPC's public contact route for statewide UxS resources, "
            "program coordination, grants, partnerships, and investment questions."
        ),
        "activity_source_url": SOURCES["vipc"][1],
        "activity_last_verified_at": CATALOG_DATE,
        "contact_text": "Virginia Unmanned Systems Center and VIPC program inquiries",
        "contact_url": SOURCES["vipc_contact"][1],
    },
    "Mid-Atlantic Aviation Partnership": {
        "activity_status": "active",
        "current_activity": (
            "MAAP remains an FAA-designated UAS test site supporting research, flight testing, "
            "evaluation, operational approvals, and safety-case development."
        ),
        "partnership_opportunities": (
            "Government, industry, and research organizations can contact MAAP about flight "
            "testing, evaluations, operational concepts, and Virginia FAA BEYOND activities."
        ),
        "activity_source_url": SOURCES["maap_about"][1],
        "activity_last_verified_at": CATALOG_DATE,
        "contact_text": "MAAP research, testing, and partnership inquiries",
        "contact_phone": "540-231-9416",
        "contact_email": "maapinfo@vt.edu",
        "contact_url": SOURCES["maap_contact"][1],
    },
    "Virginia Tech Drone Park": {
        "activity_status": "active",
        "current_activity": (
            "Virginia Tech operates the netted Drone Park for instruction, research, and "
            "controlled flight work, with adjacent laboratory and classroom support."
        ),
        "partnership_opportunities": (
            "University and external users can request scheduling; the facility notes that "
            "commercial and other third-party use may require additional arrangements."
        ),
        "activity_source_url": SOURCES["vt_drone_park"][1],
        "activity_last_verified_at": CATALOG_DATE,
        "contact_text": "Virginia Tech Drone Park scheduling and facility inquiries",
        "contact_phone": "540-231-7303",
        "contact_email": "VTDronePark@vt.edu",
        "contact_url": SOURCES["vt_drone_park"][1],
        "owner_operator": ("Virginia Tech Institute for Critical Technology and Applied Science"),
        "development_status": "operational",
        "development_notes": (
            "The published facility is an operating research and teaching site. No claim is "
            "made that land or facility space is generally available for development."
        ),
        "infrastructure_access": (
            "Approximately 300-by-120-by-85-foot netted flight enclosure with adjacent "
            "laboratory, classroom, work, and observation space."
        ),
        "development_source_url": SOURCES["vt_drone_park"][1],
        "development_last_verified_at": CATALOG_DATE,
    },
    "ODU Institute for Autonomous and Connected Systems": {
        "activity_status": "active",
        "current_activity": (
            "IACS coordinates cross-domain work in uncrewed aerial, surface, and underwater "
            "vehicles, robotics, connected transportation, sensing, and artificial intelligence."
        ),
        "partnership_opportunities": (
            "The institute invites engagement with industry, government, and community "
            "partners through its published institute contact."
        ),
        "activity_source_url": SOURCES["odu_iacs"][1],
        "activity_last_verified_at": CATALOG_DATE,
        "contact_text": "IACS research and partnership inquiries",
        "contact_phone": "757-683-3470",
        "contact_email": "hchaoui@odu.edu",
        "contact_url": SOURCES["odu_iacs"][1],
    },
    "ODU Maritime Autonomous Systems Test Site": {
        "activity_status": "active",
        "current_activity": (
            "ODU and the City of Norfolk operate the Willoughby Bay site for maritime autonomy "
            "research and testing with direct access to regional waterways."
        ),
        "partnership_opportunities": (
            "Research and external-partnership questions can be routed through ODU's National "
            "Security Institute."
        ),
        "activity_source_url": SOURCES["odu_masts"][1],
        "activity_last_verified_at": CATALOG_DATE,
        "contact_text": "ODU National Security Institute research and partnership inquiries",
        "contact_email": "research@odu.edu",
        "contact_url": SOURCES["odu_nsi"][1],
        "owner_operator": "Old Dominion University and the City of Norfolk",
        "development_status": "operational",
        "development_notes": (
            "The site opened in 2025 as an operating research and test facility. Published "
            "materials do not describe generally available land or commercial space."
        ),
        "infrastructure_access": (
            "Floating dock, half-ton crane, covered workspace, utilities, and an 18-foot chase "
            "boat, with water access from Willoughby Bay to the Chesapeake Bay and Atlantic."
        ),
        "development_source_url": SOURCES["odu_maritime_conference"][1],
        "development_last_verified_at": CATALOG_DATE,
    },
    "HII Unmanned Systems Center of Excellence": {
        "activity_status": "active",
        "current_activity": (
            "HII maintains an Uncrewed Systems business spanning unmanned undersea and surface "
            "platforms and autonomy software; the Hampton center is its publicly documented "
            "purpose-built production and test campus."
        ),
        "partnership_opportunities": (
            "Business and supplier inquiries can be routed through HII's public corporate "
            "contact channel."
        ),
        "activity_source_url": SOURCES["hii_mission_technologies"][1],
        "activity_last_verified_at": CATALOG_DATE,
        "owner_operator": "HII",
        "development_status": "operational",
        "development_notes": (
            "HII described a 20-acre campus and Hampton documented completion and occupancy of "
            "the first 22,000-square-foot building. Campus size is not presented as available "
            "acreage."
        ),
        "infrastructure_access": (
            "Purpose-built prototyping, production, testing, and digital-manufacturing campus "
            "for uncrewed systems."
        ),
        "development_source_url": SOURCES["hii_center_completion"][1],
        "development_last_verified_at": CATALOG_DATE,
    },
    "Longbow Unmanned Systems Research and Test Center": {
        "activity_status": "active",
        "current_activity": (
            "The center publicly describes ongoing support for research, validation, and "
            "demonstration work across air, land, and maritime uncrewed systems."
        ),
        "partnership_opportunities": (
            "The center states that it is seeking partnerships and provides a public inquiry "
            "form for prospective users and collaborators."
        ),
        "activity_source_url": SOURCES["longbow_current"][1],
        "activity_last_verified_at": CATALOG_DATE,
        "contact_text": "Research, testing, and partnership inquiries",
        "contact_url": SOURCES["longbow_current"][1],
    },
    "Wallops Research Park": {
        "activity_status": "developing",
        "current_activity": (
            "Accomack County markets the park for private aerospace, UAS, launch, research, and "
            "education development adjoining the Wallops federal and commercial space cluster."
        ),
        "partnership_opportunities": (
            "Prospective developers and aerospace organizations can use the county's public "
            "economic-development route to discuss current parcels and project requirements."
        ),
        "activity_source_url": SOURCES["wallops_research_park"][1],
        "activity_last_verified_at": CATALOG_DATE,
        "contact_text": "Accomack County economic-development and site inquiries",
        "contact_phone": "757-787-5700",
        "contact_url": SOURCES["wallops_research_park"][1],
        "development_status": "development-ready",
        "development_notes": (
            "The county describes the park as ready for private development. No acreage is "
            "reported here because the reviewed page does not identify a current available-acre "
            "figure."
        ),
        "infrastructure_access": (
            "Completed roads and utilities, a 1,200-foot taxiway connection, and proximity to "
            "Wallops runways, restricted airspace, payload processing, and UAS test activity."
        ),
        "development_source_url": SOURCES["wallops_research_park"][1],
        "development_last_verified_at": CATALOG_DATE,
    },
    "Newport News AirCommerce Park": {
        "activity_status": "developing",
        "current_activity": (
            "Newport News and the Peninsula Airport Commission are advancing site-readiness "
            "work for aviation and aerospace development around the airport."
        ),
        "partnership_opportunities": (
            "Aviation, aerospace, and UAS companies can contact Newport News Economic "
            "Development for current site information and project assistance."
        ),
        "activity_source_url": SOURCES["aircommerce_growth"][1],
        "activity_last_verified_at": CATALOG_DATE,
        "owner_operator": (
            "Peninsula Airport Commission (property owner); Newport News Economic Development "
            "Authority (site-readiness partner)"
        ),
        "available_acreage": 280,
        "development_status": "in-development",
        "development_notes": (
            "The reviewed EDA page describes 280 available acres at AirCommerce Park West and "
            "50 additional undeveloped acres at AirCommerce Park East. Only the 280 acres "
            "explicitly described as available are stored in the acreage field."
        ),
        "infrastructure_access": (
            "Airport-adjacent development land with runway access potential, corporate hangars, "
            "and planned site-readiness improvements."
        ),
        "development_source_url": SOURCES["aircommerce_growth"][1],
        "development_last_verified_at": CATALOG_DATE,
    },
    "AeroVironment Corporate Headquarters": {
        "activity_status": "active",
        "current_activity": (
            "AeroVironment develops autonomous systems and related capabilities across air, "
            "land, sea, space, and cyber domains from its Arlington headquarters."
        ),
        "partnership_opportunities": (
            "AeroVironment's MacCready Works page identifies collaboration with defense, "
            "research, and technology organizations and provides a public partnership route."
        ),
        "activity_source_url": SOURCES["aerovironment_partners"][1],
        "activity_last_verified_at": CATALOG_DATE,
        "contact_text": "Corporate and business inquiries",
        "contact_phone": "703-418-2828",
        "contact_url": SOURCES["aerovironment_contact"][1],
    },
    "Aurora Flight Sciences": {
        "activity_status": "active",
        "current_activity": (
            "Aurora, a Boeing company, develops advanced aircraft and autonomy technologies from "
            "its Manassas headquarters and other facilities."
        ),
        "partnership_opportunities": (
            "Product, business-development, and general inquiries can use Aurora's published "
            "sales and headquarters contacts."
        ),
        "activity_source_url": SOURCES["aurora_contact"][1],
        "activity_last_verified_at": CATALOG_DATE,
        "contact_text": "Product and business-development inquiries",
        "contact_phone": "703-369-3633",
        "contact_email": "sales@aurora.aero",
        "contact_url": SOURCES["aurora_contact"][1],
    },
    "ANRA Technologies": {
        "activity_status": "active",
        "current_activity": (
            "ANRA continues to deploy airspace and mission-management technology for commercial "
            "drone operations, UTM, UAM, and airspace-security integration."
        ),
        "partnership_opportunities": (
            "Organizations can request a consultation through ANRA's airspace-management page."
        ),
        "activity_source_url": SOURCES["anra_current"][1],
        "activity_last_verified_at": CATALOG_DATE,
        "contact_text": "Airspace-management consultation and business inquiries",
        "contact_url": SOURCES["anra_partnership"][1],
    },
    "Advanced Aircraft Company": {
        "activity_status": "active",
        "current_activity": (
            "Advanced Aircraft Company publishes its HAMR hybrid multirotor UAS product and "
            "Virginia engineering and manufacturing contact information."
        ),
        "partnership_opportunities": (
            "Product, engineering, and business inquiries can use the company's published "
            "Hampton contact information."
        ),
        "activity_source_url": SOURCES["aac_products"][1],
        "activity_last_verified_at": CATALOG_DATE,
        "contact_text": "Product, engineering, and business inquiries",
        "contact_phone": "757-325-6712",
        "contact_email": "info@flyaac.com",
        "contact_url": SOURCES["aac_products"][1],
    },
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
    "Salem": (37.293, -80.056),
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
    "Autonomous Flight Technologies": {
        "address_line": "172 East Main Street",
        "city": "Salem",
        "postal_code": "24153",
        "latitude": 37.293087,
        "longitude": -80.055796,
        "location_precision": "exact",
        "source": (
            "Autonomous Flight Technologies Salem office and employment information",
            SOURCES["autonomous_flight_location"][1],
        ),
    },
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
    "Virginia Unmanned Systems Center": {
        "address_line": "313 East Broad Street",
        "postal_code": "23219",
        "latitude": 37.543832,
        "longitude": -77.439186,
        "source": (
            "Virginia Innovation Partnership Corporation contact information",
            SOURCES["vipc_contact"][1],
        ),
    },
    "Virginia Tech Drone Park": {
        "address_line": "2143 Oak Lane",
        "postal_code": "24061",
        "latitude": 37.224100,
        "longitude": -80.428600,
        "source": (
            "Virginia Tech Drone Park facility and scheduling information",
            SOURCES["vt_drone_park"][1],
        ),
    },
    "AeroVironment Corporate Headquarters": {
        "address_line": "241 18th Street South, Suite 650",
        "postal_code": "22202",
        "latitude": 38.857634,
        "longitude": -77.050002,
        "source": (
            "AeroVironment contact information",
            SOURCES["aerovironment_contact"][1],
        ),
    },
    "Aurora Flight Sciences": {
        "address_line": "9950 Wakeman Drive",
        "postal_code": "20110",
        "latitude": 38.728261,
        "longitude": -77.512034,
        "source": (
            "Aurora Flight Sciences contact information",
            SOURCES["aurora_contact"][1],
        ),
    },
    "ANRA Technologies": {
        "address_line": "11710 Plaza America Drive, Suite 200",
        "postal_code": "20190",
        "latitude": 38.951363,
        "longitude": -77.347340,
        "source": (
            "ANRA Technologies Reston location",
            SOURCES["anra_location"][1],
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
        "address_line": "1100 Exploration Way, Suite 316M",
        "postal_code": "23666",
        "latitude": 37.082521,
        "longitude": -76.399763,
        "source": (
            "Advanced Aircraft Company UAS products and public contact information",
            SOURCES["aac_products"][1],
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
        "address_line": "",
        "postal_code": "",
        "latitude": 36.8529,
        "longitude": -75.9780,
        "location_precision": "locality",
        "source": (
            "DroneUp current airspace and UAS technology operations",
            "https://www.droneup.com/",
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
        "address_line": "Hampton Roads Center - North Campus",
        "postal_code": "23666",
        "latitude": 37.074905,
        "longitude": -76.402317,
        "source": (
            "HII Unmanned Systems Center of Excellence",
            SOURCES["hii_uxs"][1],
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
            "U.S. Small Business Innovation Research portfolio: The Longbow Group",
            "https://www.sbir.gov/portfolio/1664155",
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
            "National Institute of Aerospace",
            "https://www.nianet.org/",
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
            "Virginia Military Institute location",
            "https://www.vmi.edu/about/our-location/",
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
        "source": (
            "Old Dominion University contact information",
            "https://www.odu.edu/about/contact",
        ),
    },
    "ODU Uncrewed Systems Design and Development Minor": {
        "address_line": "5115 Hampton Boulevard",
        "postal_code": "23529",
        "latitude": 36.889280,
        "longitude": -76.303179,
        "source": (
            "Old Dominion University contact information",
            "https://www.odu.edu/about/contact",
        ),
    },
    "ODU Drone Certificate Program": {
        "address_line": "5115 Hampton Boulevard",
        "postal_code": "23529",
        "latitude": 36.889280,
        "longitude": -76.303179,
        "source": (
            "Old Dominion University contact information",
            "https://www.odu.edu/about/contact",
        ),
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
        "source": (
            "Hampton Division of Fire and Rescue",
            "https://www.hampton.gov/244/Fire-Rescue",
        ),
    },
    "Chesapeake Police UAS Team": {
        "address_line": "304 Albemarle Drive",
        "postal_code": "23322",
        "latitude": 36.717383,
        "longitude": -76.247114,
        "source": (
            "Chesapeake Police Department",
            "https://www.cityofchesapeake.net/727/Police-Department",
        ),
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
        "address_line": "",
        "postal_code": "",
        "latitude": 38.846,
        "longitude": -77.307,
        "location_precision": "locality",
        "source": (
            "DZYNE current locations and Ondas Sentinel ownership",
            "https://dzyne.com/contact-us/",
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
    "Mid-Atlantic Aviation Partnership": {
        "address_line": "1991 Kraft Drive, Building 19",
        "postal_code": "24060",
        "latitude": 37.202048,
        "longitude": -80.409798,
        "location_precision": "site",
        "source": (
            "Virginia Tech ICTAS Corporate Research Center facility",
            "https://ictas.vt.edu/Facilities/ictascrc.html",
        ),
    },
    "Virginia Tech Transportation Institute": {
        "address_line": "3500 Transportation Research Plaza",
        "postal_code": "24061",
        "latitude": 37.187786,
        "longitude": -80.397174,
        "location_precision": "exact",
        "source": (
            "Virginia Tech Transportation Institute contact information",
            "https://www.vtti.vt.edu/contact/index.html",
        ),
    },
    "Virginia Smart Road": {
        "address_line": "3500 Transportation Research Plaza",
        "postal_code": "24061",
        "latitude": 37.187786,
        "longitude": -80.397174,
        "location_precision": "site",
        "source": (
            "Virginia Tech Transportation Institute Smart Roads facility",
            "https://www.vtti.vt.edu/facilities/virginia-smart-roads.html",
        ),
    },
    "Kentland Experimental Aerial Systems Laboratory": {
        "address_line": "Kentland Farm, 5250 Whitethorne Road",
        "postal_code": "24060",
        "latitude": 37.199869,
        "longitude": -80.564314,
        "location_precision": "site",
        "source": (
            "Virginia Tech Kentland Farm facility information",
            "https://www.cals.vt.edu/research/facilities.html",
        ),
    },
    "NASA Wallops Flight Facility": {
        "address_line": "34200 Fulton Street",
        "postal_code": "23337",
        "latitude": 37.940000,
        "longitude": -75.466000,
        "location_precision": "site",
        "source": (
            "NASA Wallops Flight Facility mailing and site address",
            "https://www.nasa.gov/wallops/visitor-center/plan-your-visit/",
        ),
    },
    "Mid-Atlantic Regional Spaceport": {
        "address_line": "7414 Atlantic Road",
        "postal_code": "23337",
        "latitude": 37.933422,
        "longitude": -75.479662,
        "location_precision": "exact",
        "source": (
            "Virginia Spaceport Authority contact information",
            "https://www.vaspace.org/contact-us",
        ),
    },
    "Institute for Advanced Learning and Research": {
        "address_line": "150 Slayton Avenue",
        "postal_code": "24540",
        "latitude": 36.579466,
        "longitude": -79.356172,
        "location_precision": "exact",
        "source": (
            "Institute for Advanced Learning and Research contact information",
            "https://www.ialr.org/contact/",
        ),
    },
    "IALR AgBOT Precision Agriculture Program": {
        "address_line": "150 Slayton Avenue",
        "postal_code": "24540",
        "latitude": 36.579466,
        "longitude": -79.356172,
        "location_precision": "site",
        "source": (
            "Institute for Advanced Learning and Research contact information",
            "https://www.ialr.org/contact/",
        ),
    },
    "GO TEC Automation and Robotics Talent Pathway": {
        "address_line": "150 Slayton Avenue",
        "postal_code": "24540",
        "latitude": 36.579466,
        "longitude": -79.356172,
        "location_precision": "site",
        "source": (
            "Institute for Advanced Learning and Research contact information",
            "https://www.ialr.org/contact/",
        ),
    },
    "UVA Link Lab": {
        "address_line": "Olsson Hall, 151 Engineer's Way",
        "postal_code": "22904",
        "latitude": 38.032666,
        "longitude": -78.510787,
        "location_precision": "exact",
        "source": (
            "UVA Link Lab visitor information",
            "https://engineering.virginia.edu/labs-groups/link-lab/visit",
        ),
    },
    "George Mason RobotiXX Laboratory": {
        "address_line": "3401 Fairfax Drive",
        "postal_code": "22201",
        "latitude": 38.884422,
        "longitude": -77.101047,
        "location_precision": "site",
        "source": (
            "George Mason RobotiXX Laboratory faculty profile",
            "https://people.cs.gmu.edu/~xiao/xuesu_website_files/CV_Xiao.pdf",
        ),
    },
    "Amherst County Fire and EMS Drone Program": {
        "address_line": "119 Taylor Street",
        "postal_code": "24521",
        "latitude": 37.585554,
        "longitude": -79.049827,
        "location_precision": "exact",
        "source": (
            "Amherst County Fire and EMS contact information",
            "https://www.countyofamherst.com/department/index.php?structureid=23",
        ),
    },
    "Staunton Police Department UAS Program": {
        "address_line": "116 West Beverley Street",
        "postal_code": "24401",
        "latitude": 38.149343,
        "longitude": -79.073899,
        "location_precision": "exact",
        "source": (
            "Staunton Police Department contact information",
            "https://www.ci.staunton.va.us/departments/police",
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
    ("Fort Walker", "Bowling Green", "Fredericksburg Region"),
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
            "VCU ARVL Robotic Drone System",
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
        "VCU ARVL Robotic Drone System",
        "facility",
        "Richmond",
        "Greater Richmond",
        "research_air",
        "Indoor drone system supporting swarm sensing, control, computer vision, and coordinated air-ground robotics research.",
        "vcu_arvl",
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
        "Former Dedrone Washington-Area Headquarters",
        "organization",
        "Sterling",
        "Northern Virginia",
        "company_cross",
        "Former Sterling headquarters of Dedrone, retained as a historical Virginia ecosystem record after Axon acquired the company in 2024.",
        "dedrone",
    ),
    (
        "DroneUp",
        "organization",
        "Virginia Beach",
        "Hampton Roads",
        "company_air",
        "Virginia Beach-founded company now focused on airspace management, regulatory enablement, and autonomous UAS operations technology.",
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
        "Salem",
        "Roanoke Valley",
        "company_air",
        "Salem developer of unmanned aircraft, avionics, counter-UAS products, and autonomous-flight technologies.",
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
        "Sheriff's Office drone operations documented in 2026 public academy and youth-program materials.",
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
            "Fairfax location of DZYNE, part of Ondas Sentinel, developing long-endurance unmanned aircraft and counter-UAS capabilities.",
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

DCJS_UNRESOLVED_JURISDICTION_UAS_ASSETS = [
    ("Bath County", "Warm Springs", "Shenandoah Valley"),
    ("Buchanan County", "Grundy", "Southwest Virginia"),
    ("Town of Chilhowie", "Chilhowie", "Southwest Virginia"),
    ("Town of Chincoteague", "Chincoteague", "Eastern Shore"),
    ("City of Manassas", "Manassas", "Northern Virginia"),
    ("Town of New Market", "New Market", "Shenandoah Valley"),
    ("Pittsylvania County", "Chatham", "Southside Virginia"),
    ("Town of Rocky Mount", "Rocky Mount", "Roanoke Valley"),
    ("Town of Scottsville", "Scottsville", "Central Virginia"),
    ("Smyth County", "Marion", "Southwest Virginia"),
    ("Southampton County", "Courtland", "Southside Virginia"),
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
    for jurisdiction, place, region in DCJS_UNRESOLVED_JURISDICTION_UAS_ASSETS
)

CURATED_ASSETS.extend(
    [
        (
            "Amherst County Fire and EMS Drone Program",
            "program",
            "Amherst",
            "Lynchburg Region",
            "public_safety",
            "County Fire and EMS drone capability documented in emergency-services minutes and the department's insured equipment schedule.",
            (
                "amherst_fire_drone",
                "amherst_fire_equipment",
                "amherst_fire_contact",
                "dcjs_awards",
                "dcjs_drone",
            ),
        ),
        (
            "Staunton Police Department UAS Program",
            "program",
            "Staunton",
            "Shenandoah Valley",
            "public_safety",
            "Police unmanned-aircraft capability documented through a city homeland-security grant appropriation and a CY 2026 replacement award.",
            (
                "staunton_police_uas",
                "staunton_police_contact",
                "dcjs_awards",
                "dcjs_drone",
            ),
        ),
        (
            "Ashland Police Department Drone Program",
            "program",
            "Ashland",
            "Greater Richmond",
            "public_safety",
            "Police drone program used for incident response, infrared search support, and public-safety operations.",
            ("ashland_police_drone", "dcjs_awards", "dcjs_drone"),
        ),
        (
            "Haymarket Police Department Drone Program",
            "program",
            "Haymarket",
            "Northern Virginia",
            "public_safety",
            "Town police drone program documented as fully implemented and supported by a CY 2026 replacement award.",
            ("haymarket_police_drone", "dcjs_awards", "dcjs_drone"),
        ),
        (
            "Madison County Sheriff's Office UAS Program",
            "program",
            "Madison",
            "Central Virginia",
            "public_safety",
            "Sheriff's Office unmanned-aircraft capability supported by a CY 2026 DCJS replacement grant.",
            ("madison_sheriff_drone", "dcjs_awards", "dcjs_drone"),
        ),
        (
            "Occoquan Police Department Public Safety Drone Program",
            "program",
            "Occoquan",
            "Northern Virginia",
            "public_safety",
            "Police-led public-safety drone capability supported by municipal purchases, training, and a CY 2026 replacement grant.",
            ("occoquan_police_drone", "dcjs_awards", "dcjs_drone"),
        ),
        (
            "Radford City Police Department Drone Program",
            "program",
            "Radford",
            "New River Valley",
            "public_safety",
            "Police drone program replacing an existing DJI Mavic 3T with a compliant Skydio X10 and accessories.",
            ("radford_police_drone", "dcjs_awards", "dcjs_drone"),
        ),
        (
            "Wise County Sheriff's Office Drone Program",
            "program",
            "Wise",
            "Southwest Virginia",
            "public_safety",
            "Sheriff's Office drone capability supported by a CY 2026 DCJS unmanned-aircraft grant.",
            ("wise_sheriff_drone", "dcjs_awards", "dcjs_drone"),
        ),
        (
            "Wythe County Sheriff's Office Drone Program",
            "program",
            "Wytheville",
            "Southwest Virginia",
            "public_safety",
            "Sheriff's Office unmanned-aircraft capability supported by a CY 2026 DCJS replacement grant.",
            ("wythe_sheriff_drone", "dcjs_awards", "dcjs_drone"),
        ),
    ]
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

# Direct UxS companies and facilities researched after the August 21 full-catalog
# audit. These records stay explicit because their source-backed profile, activity,
# and location details are more specific than the shared curated-asset templates.
VERIFIED_UXS_ADDITIONS = [
    {
        "name": "Analytical Mechanics Associates",
        "record_type": "organization",
        "short_description": (
            "Hampton engineering company with documented autonomous-vehicle, UAV, "
            "flight-hardware, simulation, prototyping, and test capabilities."
        ),
        "overview": (
            "Analytical Mechanics Associates (AMA) is a Hampton-headquartered engineering "
            "company supporting government and industry missions. Its public engineering "
            "profile specifically lists autonomous vehicles and UAVs alongside guidance, "
            "navigation and control, flight hardware, modeling and simulation, additive "
            "manufacturing, and 3D prototyping."
        ),
        "unmanned_systems_relevance": (
            "Provides documented engineering, analysis, simulation, prototyping, and test "
            "support applicable to uncrewed aircraft and autonomous vehicles."
        ),
        "activity_status": "active",
        "current_activity": (
            "AMA currently markets autonomous-vehicle and UAV engineering capabilities from "
            "its Hampton headquarters, including flight hardware design, guidance and control, "
            "simulation, additive manufacturing, and prototyping."
        ),
        "activity_source_url": (
            "https://www.ama-inc.com/engineering/ENG_MissionAnalysisDesign.shtml"
        ),
        "activity_last_verified_at": "2026-08-24",
        "address_line": "21 Enterprise Parkway, Suite 300",
        "city": "Hampton",
        "state": "VA",
        "postal_code": "23666",
        "latitude": 37.054285,
        "longitude": -76.408421,
        "location_precision": "exact",
        "region": "Hampton Roads",
        "strategic_categories": [
            "Companies and solution providers",
            "Research and technical depth",
            "Core unmanned-systems asset",
        ],
        "platform_domains": [
            "Unmanned aircraft systems",
            "Ground vehicles and robotics",
            "Cross-domain autonomy",
        ],
        "capabilities": [
            "Systems engineering and integration",
            "Simulation, digital twins, and synthetic environments",
            "Testing, evaluation, verification, and validation",
            "Manufacturing, materials, and prototyping",
        ],
        "missions": ["Training and experimentation", "Logistics and contested logistics"],
        "website_url": ("https://www.ama-inc.com/engineering/ENG_MissionAnalysisDesign.shtml"),
        "contact_text": "AMA general inquiries",
        "contact_phone": "757-865-0000",
        "contact_email": "info@ama-inc.com",
        "contact_url": "https://www.ama-inc.com/contact",
        "sources": [
            {
                "title": "AMA autonomous-vehicle and UAV engineering capabilities",
                "url": "https://www.ama-inc.com/engineering/ENG_MissionAnalysisDesign.shtml",
            },
            {
                "title": "AMA Hampton headquarters and public contact information",
                "url": "https://www.ama-inc.com/contact",
            },
        ],
        "provenance": "curated-public-source",
    },
    {
        "name": "Austal USA Advanced Technologies and Solutions",
        "record_type": "organization",
        "short_description": (
            "Charlottesville division dedicated to autonomous maritime platforms, AI-enabled "
            "systems, USVs, and future UUV capabilities."
        ),
        "overview": (
            "Austal USA's Charlottesville-based Advanced Technologies and Solutions division "
            "develops and integrates autonomous maritime platforms and mission technologies. "
            "The company identifies unmanned surface vehicles as an active portfolio and "
            "undersea vehicles as a growth area."
        ),
        "unmanned_systems_relevance": (
            "Provides documented design, engineering, integration, and life-cycle capabilities "
            "for autonomous ships, unmanned surface vessels, and future undersea systems."
        ),
        "activity_status": "active",
        "current_activity": (
            "The Charlottesville division is currently dedicated to advanced maritime solutions "
            "and autonomous systems, including AI-enabled platforms and a USV portfolio."
        ),
        "activity_source_url": "https://www.austalusa.com/solutions",
        "activity_last_verified_at": "2026-08-24",
        "address_line": "501 Locust Avenue, Suite 100",
        "city": "Charlottesville",
        "state": "VA",
        "postal_code": "22902",
        "latitude": 38.032396,
        "longitude": -78.47094,
        "location_precision": "exact",
        "region": "Central Virginia",
        "strategic_categories": [
            "Companies and solution providers",
            "Manufacturing and supply chain",
            "Core unmanned-systems asset",
        ],
        "platform_domains": ["Maritime surface systems", "Undersea systems"],
        "capabilities": [
            "Autonomy and artificial intelligence",
            "Systems engineering and integration",
            "Manufacturing, materials, and prototyping",
            "Operations, maintenance, and sustainment",
        ],
        "missions": [
            "Maritime domain awareness",
            "Logistics and contested logistics",
            "ISR",
        ],
        "website_url": "https://www.austalusa.com/solutions",
        "contact_text": "Austal USA public inquiry form",
        "contact_phone": "",
        "contact_email": "",
        "contact_url": "https://www.austalusa.com/contact-us",
        "sources": [
            {
                "title": "Austal USA autonomous maritime solutions",
                "url": "https://www.austalusa.com/solutions",
            },
            {
                "title": "Austal USA Charlottesville office",
                "url": "https://www.austalusa.com/contact-us",
            },
        ],
        "provenance": "curated-public-source",
    },
    {
        "name": "Devorto",
        "record_type": "organization",
        "short_description": (
            "Hampton developer of the TURN high-altitude, long-endurance uncrewed aircraft "
            "concept for communications, sensing, and persistent missions."
        ),
        "overview": (
            "Devorto is a Hampton aerospace company developing the Tethered Uni-Rotor Network "
            "(TURN), a high-altitude, long-endurance aircraft concept intended for persistent "
            "communications, sensing, environmental monitoring, and defense missions. Public "
            "NASA and SBIR records document earlier technical research behind the concept."
        ),
        "unmanned_systems_relevance": (
            "Develops a documented uncrewed high-altitude platform concept and associated "
            "propulsion, controls, navigation, communications, and payload architecture."
        ),
        "activity_status": "developing",
        "current_activity": (
            "Devorto publicly describes ongoing development of TURN variants ranging from a "
            "solar high-altitude platform to smaller commercial and defense UAS concepts."
        ),
        "activity_source_url": "https://devorto.io/",
        "activity_last_verified_at": "2026-08-24",
        "address_line": "16 Murray Street",
        "city": "Hampton",
        "state": "VA",
        "postal_code": "23651",
        "latitude": 37.007896,
        "longitude": -76.311615,
        "location_precision": "exact",
        "region": "Hampton Roads",
        "strategic_categories": [
            "Companies and solution providers",
            "Research and technical depth",
            "Core unmanned-systems asset",
        ],
        "platform_domains": ["Unmanned aircraft systems", "Space-enabled services"],
        "capabilities": [
            "Propulsion, batteries, fuels, and energy systems",
            "Autonomy and artificial intelligence",
            "Navigation and positioning",
            "Command, control, and communications",
        ],
        "missions": ["Communications relay", "Environmental monitoring", "ISR"],
        "website_url": "https://devorto.io/",
        "contact_text": "Devorto company inquiries",
        "contact_phone": "757-703-4850",
        "contact_email": "info@devorto.io",
        "contact_url": "https://devorto.io/",
        "sources": [
            {
                "title": "Devorto TURN aircraft and contact information",
                "url": "https://devorto.io/",
            },
            {
                "title": "NASA NIAC TURN feasibility study",
                "url": (
                    "https://www.nasa.gov/wp-content/uploads/2019/10/"
                    "moore_2013_phi_eternalflight_-_tagged.pdf"
                ),
            },
        ],
        "provenance": "curated-public-source",
    },
    {
        "name": "DroneShield U.S. Headquarters",
        "record_type": "organization",
        "short_description": (
            "Warrenton U.S. headquarters for a counter-UAS company specializing in RF sensing, "
            "AI, sensor fusion, electronic warfare, and system integration."
        ),
        "overview": (
            "DroneShield's Warrenton office is the company's United States headquarters. The "
            "company develops counter-UAS detection, identification, tracking, and response "
            "solutions for terrestrial, maritime, and airborne platforms."
        ),
        "unmanned_systems_relevance": (
            "Develops documented counter-UAS products and integration capabilities using RF "
            "sensing, artificial intelligence, sensor fusion, edge computing, and electronic "
            "warfare."
        ),
        "activity_status": "active",
        "current_activity": (
            "DroneShield announced a 2026 integration of its DroneSentry-X Mk2 counter-UAS "
            "system with Overland AI's autonomous ground vehicle and identified Warrenton as "
            "the release location."
        ),
        "activity_source_url": (
            "https://www.droneshield.com/media/press-releases/"
            "droneshield-overland-ai-advance-autonomous-ground-protection-interoperability"
        ),
        "activity_last_verified_at": "2026-08-24",
        "address_line": "7140-B Farm Station Road",
        "city": "Warrenton",
        "state": "VA",
        "postal_code": "20187",
        "latitude": 38.744348,
        "longitude": -77.676112,
        "location_precision": "exact",
        "region": "Northern Virginia",
        "strategic_categories": [
            "Companies and solution providers",
            "Manufacturing and supply chain",
            "Core unmanned-systems asset",
        ],
        "platform_domains": [
            "Counter-UAS",
            "Ground vehicles and robotics",
            "Cross-domain autonomy",
        ],
        "capabilities": [
            "Perception, sensing, and sensor fusion",
            "Autonomy and artificial intelligence",
            "Systems engineering and integration",
            "Manufacturing, materials, and prototyping",
        ],
        "missions": ["Counter-UAS", "Force protection and installation security"],
        "website_url": "https://www.droneshield.com/connect-with-us",
        "contact_text": "DroneShield U.S. headquarters",
        "contact_phone": "540-215-8383",
        "contact_email": "",
        "contact_url": "https://www.droneshield.com/connect-with-us",
        "sources": [
            {
                "title": "DroneShield U.S. headquarters and capabilities",
                "url": "https://www.droneshield.com/connect-with-us",
            },
            {
                "title": "DroneShield and Overland AI counter-UAS integration",
                "url": (
                    "https://www.droneshield.com/media/press-releases/"
                    "droneshield-overland-ai-advance-autonomous-ground-protection-"
                    "interoperability"
                ),
            },
        ],
        "provenance": "curated-public-source",
    },
    {
        "name": "Fairlead Maritime Systems",
        "record_type": "organization",
        "short_description": (
            "Portsmouth shipbuilder and systems integrator with active unmanned-platform work "
            "and a 2026 partnership to scale AEGIR unmanned surface vessel production."
        ),
        "overview": (
            "Fairlead is a Portsmouth-headquartered maritime manufacturer and systems "
            "integrator with multiple Virginia industrial waterfront facilities. The company "
            "reports active contracts involving unmanned platforms and announced a partnership "
            "with SNC to establish scalable domestic production of AEGIR USVs."
        ),
        "unmanned_systems_relevance": (
            "Provides documented maritime manufacturing, modular construction, systems "
            "integration, and sustainment capacity for unmanned surface vessels."
        ),
        "activity_status": "active",
        "current_activity": (
            "Fairlead and SNC announced a May 2026 partnership to domestically produce AEGIR "
            "unmanned surface vessels using Fairlead's shipbuilding and systems-integration "
            "capacity. The public announcement does not identify a single production address."
        ),
        "activity_source_url": "https://fairlead.com/about/press-releases/snc-and-fairlead/",
        "activity_last_verified_at": "2026-08-24",
        "address_line": "650 Chautauqua Avenue",
        "city": "Portsmouth",
        "state": "VA",
        "postal_code": "23707",
        "latitude": 36.843529,
        "longitude": -76.332593,
        "location_precision": "exact",
        "region": "Hampton Roads",
        "strategic_categories": [
            "Companies and solution providers",
            "Manufacturing and supply chain",
            "Core unmanned-systems asset",
        ],
        "platform_domains": ["Maritime surface systems", "Undersea systems"],
        "capabilities": [
            "Systems engineering and integration",
            "Manufacturing, materials, and prototyping",
            "Operations, maintenance, and sustainment",
        ],
        "missions": [
            "Maritime domain awareness",
            "Logistics and contested logistics",
            "Force protection and installation security",
        ],
        "website_url": "https://fairlead.com/",
        "contact_text": "Fairlead corporate headquarters",
        "contact_phone": "757-384-1957",
        "contact_email": "",
        "contact_url": "https://fairlead.com/",
        "sources": [
            {
                "title": "Fairlead capabilities and Virginia headquarters",
                "url": "https://fairlead.com/",
            },
            {
                "title": "SNC and Fairlead AEGIR USV production partnership",
                "url": "https://fairlead.com/about/press-releases/snc-and-fairlead/",
            },
        ],
        "provenance": "curated-public-source",
    },
    {
        "name": "Heven AeroTech Winchester Innovation and Manufacturing Campus",
        "record_type": "facility",
        "short_description": (
            "Winchester UAS engineering, manufacturing, flight-test, payload-integration, and "
            "hydrogen-systems campus."
        ),
        "overview": (
            "Heven AeroTech identifies its Winchester facility as an innovation and "
            "manufacturing campus combining engineering, high-volume manufacturing, flight "
            "testing, payload integration, and training. Current job listings document drone "
            "assembly, production, integration, and hydrogen-systems work in Winchester."
        ),
        "unmanned_systems_relevance": (
            "Provides documented Virginia production, integration, propulsion, and flight-test "
            "capacity for hydrogen-powered and tactical uncrewed aircraft."
        ),
        "activity_status": "active",
        "current_activity": (
            "Heven currently advertises Winchester manufacturing, production, integration, "
            "hydrogen engineering, and UAS flight-operations roles tied to the campus."
        ),
        "activity_source_url": "https://hevenaerotech.com/work-with-us/",
        "activity_last_verified_at": "2026-08-24",
        "city": "Winchester",
        "state": "VA",
        "postal_code": "",
        "latitude": 39.185,
        "longitude": -78.163,
        "location_precision": "locality",
        "region": "Shenandoah Valley",
        "strategic_categories": [
            "Manufacturing and supply chain",
            "Test and operational environments",
            "Companies and solution providers",
            "Core unmanned-systems asset",
        ],
        "platform_domains": ["Unmanned aircraft systems"],
        "capabilities": [
            "Manufacturing, materials, and prototyping",
            "Propulsion, batteries, fuels, and energy systems",
            "Testing, evaluation, verification, and validation",
            "Payloads and mission systems",
        ],
        "missions": [
            "ISR",
            "Logistics and contested logistics",
            "Public safety and emergency response",
            "Training and experimentation",
        ],
        "website_url": "https://hevenaerotech.com/company/",
        "contact_text": "Heven AeroTech company inquiries",
        "contact_phone": "877-726-6269",
        "contact_email": "info@hevenaerotech.com",
        "contact_url": "https://hevenaerotech.com/company/",
        "sources": [
            {
                "title": "Heven AeroTech Winchester innovation and manufacturing campus",
                "url": "https://hevenaerotech.com/company/",
            },
            {
                "title": "Heven AeroTech Winchester manufacturing and UAS positions",
                "url": "https://hevenaerotech.com/work-with-us/",
            },
        ],
        "provenance": "curated-public-source",
    },
    {
        "name": "Logos Technologies",
        "record_type": "organization",
        "short_description": (
            "Fairfax developer and producer of wide-area imagery sensors, edge processing, "
            "analytics, and payloads for unmanned aircraft."
        ),
        "overview": (
            "Logos Technologies is a Fairfax sensor and analytics company whose design, "
            "development, and production teams build wide-area motion imagery and edge-data "
            "systems. Its product portfolio includes payloads designed specifically for "
            "unmanned aircraft systems."
        ),
        "unmanned_systems_relevance": (
            "Develops and produces documented UAS payloads, persistent-surveillance sensors, "
            "edge processing, and advanced analytics."
        ),
        "activity_status": "active",
        "current_activity": (
            "Logos currently markets multiple UAS-oriented sensor products, including "
            "BlackKite-I, RedKite-I, and MicroKestrel, from its Fairfax operation."
        ),
        "activity_source_url": "https://www.logostech.net/products/",
        "activity_last_verified_at": "2026-08-24",
        "address_line": "2701 Prosperity Avenue, Suite 400",
        "city": "Fairfax",
        "state": "VA",
        "postal_code": "22031",
        "latitude": 38.881015,
        "longitude": -77.23358,
        "location_precision": "exact",
        "region": "Northern Virginia",
        "strategic_categories": [
            "Companies and solution providers",
            "Manufacturing and supply chain",
            "Core unmanned-systems asset",
        ],
        "platform_domains": ["Unmanned aircraft systems"],
        "capabilities": [
            "Perception, sensing, and sensor fusion",
            "Payloads and mission systems",
            "Data engineering, analytics, and edge computing",
            "Manufacturing, materials, and prototyping",
        ],
        "missions": [
            "ISR",
            "Force protection and installation security",
            "Infrastructure inspection",
        ],
        "website_url": "https://www.logostech.net/about-us/",
        "contact_text": "Logos Technologies Fairfax office",
        "contact_phone": "703-584-5725",
        "contact_email": "",
        "contact_url": "https://www.logostech.net/about-us/",
        "sources": [
            {
                "title": "Logos Technologies Fairfax office and UAS sensor capabilities",
                "url": "https://www.logostech.net/about-us/",
            },
            {
                "title": "Logos Technologies UAS sensor products",
                "url": "https://www.logostech.net/products/",
            },
        ],
        "provenance": "curated-public-source",
    },
    {
        "name": "Mare Custos U.S. Presence at IDEA Lab",
        "record_type": "organization",
        "short_description": (
            "Norfolk U.S. presence for a developer of underwater robotic inspection, sensing, "
            "sampling, and subsea maintenance systems."
        ),
        "overview": (
            "Mare Custos develops remotely operated underwater robotic systems and modular "
            "payloads for offshore inspection, environmental sampling, and subsea maintenance. "
            "In June 2026 the company established its first U.S. presence through the Hampton "
            "Roads Alliance IDEA Lab in downtown Norfolk."
        ),
        "unmanned_systems_relevance": (
            "Develops and deploys documented underwater robotic vehicles, inspection tools, "
            "sensors, and data-collection payloads."
        ),
        "activity_status": "active",
        "current_activity": (
            "Mare Custos established its first U.S. presence at the Hampton Roads Alliance IDEA "
            "Lab in Norfolk in June 2026 to develop U.S. maritime, energy, infrastructure, and "
            "defense partnerships."
        ),
        "activity_source_url": (
            "https://norfolkdevelopment.com/mare-custos-establishes-u-s-presence-in-norfolk-"
            "through-idea-lab-to-advance-maritime-robotics-and-subsea-inspection-innovation/"
        ),
        "activity_last_verified_at": "2026-08-24",
        "address_line": "3 Commercial Place, Suite 1320",
        "city": "Norfolk",
        "state": "VA",
        "postal_code": "23510",
        "latitude": 36.845514,
        "longitude": -76.288238,
        "location_precision": "site",
        "region": "Hampton Roads",
        "strategic_categories": [
            "Companies and solution providers",
            "Commercialization and capital",
            "Core unmanned-systems asset",
        ],
        "platform_domains": ["Undersea systems"],
        "capabilities": [
            "Perception, sensing, and sensor fusion",
            "Systems engineering and integration",
            "Data engineering, analytics, and edge computing",
            "Operations, maintenance, and sustainment",
        ],
        "missions": [
            "Infrastructure inspection",
            "Environmental monitoring",
            "Maritime domain awareness",
        ],
        "website_url": "https://mare-custos.com/",
        "contact_text": "Mare Custos company inquiries",
        "contact_phone": "+33 7 56 80 80 04",
        "contact_email": "contact@mare-custos.com",
        "contact_url": "https://mare-custos.com/contact/",
        "sources": [
            {
                "title": "City of Norfolk: Mare Custos IDEA Lab presence",
                "url": (
                    "https://norfolkdevelopment.com/mare-custos-establishes-u-s-presence-in-"
                    "norfolk-through-idea-lab-to-advance-maritime-robotics-and-subsea-"
                    "inspection-innovation/"
                ),
            },
            {"title": "Mare Custos underwater robotics", "url": "https://mare-custos.com/"},
            {
                "title": "Mare Custos public contact information",
                "url": "https://mare-custos.com/contact/",
            },
            {
                "title": "Hampton Roads Alliance contact and IDEA Lab location",
                "url": (
                    "https://hamptonroadsalliance.com/wp-content/uploads/2025/01/"
                    "Minutes_Board-Meeting_April-19-2024.pdf"
                ),
            },
        ],
        "provenance": "curated-public-source",
    },
    {
        "name": "Psionic",
        "record_type": "organization",
        "short_description": (
            "Hampton developer of laser-based navigation and sensing for autonomous land, air, "
            "and space vehicles operating in GPS-denied environments."
        ),
        "overview": (
            "Psionic is a Hampton company founded by former NASA engineers. It develops "
            "laser-based navigation sensors and systems that provide velocity, position, and "
            "attitude information for autonomous land, air, and space vehicles when GPS is "
            "degraded, jammed, spoofed, or unavailable."
        ),
        "unmanned_systems_relevance": (
            "Provides documented assured navigation, positioning, and sensing technology for "
            "manned and unmanned autonomous platforms."
        ),
        "activity_status": "active",
        "current_activity": (
            "Psionic currently markets SurePath navigation sensors for defense, aviation, and "
            "ground platforms and is developing an end-to-end navigation system."
        ),
        "activity_source_url": "https://psionicnav.com/",
        "activity_last_verified_at": "2026-08-24",
        "address_line": "1100 Exploration Way, Suite 209",
        "city": "Hampton",
        "state": "VA",
        "postal_code": "23666",
        "latitude": 37.082521,
        "longitude": -76.399763,
        "location_precision": "exact",
        "region": "Hampton Roads",
        "strategic_categories": [
            "Companies and solution providers",
            "Research and technical depth",
            "Core unmanned-systems asset",
        ],
        "platform_domains": [
            "Unmanned aircraft systems",
            "Ground vehicles and robotics",
            "Space-enabled services",
            "Cross-domain autonomy",
        ],
        "capabilities": [
            "Navigation and positioning",
            "Perception, sensing, and sensor fusion",
            "Systems engineering and integration",
        ],
        "missions": ["ISR", "Logistics and contested logistics", "Infrastructure inspection"],
        "website_url": "https://psionicnav.com/",
        "contact_text": "Psionic company inquiries",
        "contact_phone": "",
        "contact_email": "contactus@psionicnav.com",
        "contact_url": "https://psionicnav.com/",
        "sources": [
            {
                "title": "Psionic autonomous navigation capabilities and Hampton contact",
                "url": "https://psionicnav.com/",
            },
            {
                "title": "NASA Spinoff profile of Psionic navigation technology",
                "url": "https://spinoff.nasa.gov/Softer_Moon_Landings_for_Companies",
            },
        ],
        "provenance": "curated-public-source",
    },
    {
        "name": "SubSea Craft Virginia Beach Operations",
        "record_type": "organization",
        "short_description": (
            "Planned Virginia Beach operation for a developer of uncrewed surface vessels, "
            "subsurface craft, and subsurface-launched UAS."
        ),
        "overview": (
            "SubSea Craft is a United Kingdom maritime-technology company developing uncrewed "
            "surface vessels, submersible craft, and subsurface-launched uncrewed aircraft. In "
            "May 2026 the company announced plans to expand operations to Virginia Beach and "
            "hire leadership, operations, field-engineering, and technical staff."
        ),
        "unmanned_systems_relevance": (
            "Develops documented uncrewed surface, subsurface, and aerial platforms for "
            "maritime awareness, ISR, communications, and contested operations."
        ),
        "activity_status": "planned",
        "current_activity": (
            "SubSea Craft announced plans to establish Virginia Beach operations and recruit "
            "U.S. personnel. No specific Virginia facility address was publicly identified in "
            "the reviewed materials."
        ),
        "activity_source_url": ("https://subseacraft.com/subsea-craft-kickstarts-u-s-expansion/"),
        "activity_last_verified_at": "2026-08-24",
        "development_status": "planned",
        "development_notes": (
            "The Virginia Beach operation was publicly announced in May 2026; the catalog does "
            "not yet have evidence of an opened local facility or a public street address."
        ),
        "development_source_url": (
            "https://subseacraft.com/subsea-craft-kickstarts-u-s-expansion/"
        ),
        "development_last_verified_at": "2026-08-24",
        "city": "Virginia Beach",
        "state": "VA",
        "postal_code": "",
        "latitude": 36.853,
        "longitude": -75.978,
        "location_precision": "locality",
        "region": "Hampton Roads",
        "strategic_categories": [
            "Companies and solution providers",
            "Commercialization and capital",
            "Core unmanned-systems asset",
        ],
        "platform_domains": [
            "Maritime surface systems",
            "Undersea systems",
            "Unmanned aircraft systems",
        ],
        "capabilities": [
            "Autonomy and artificial intelligence",
            "Systems engineering and integration",
            "Payloads and mission systems",
        ],
        "missions": [
            "Maritime domain awareness",
            "ISR",
            "Communications relay",
            "Force protection and installation security",
        ],
        "website_url": "https://subseacraft.com/",
        "contact_text": "Company inquiries regarding the announced Virginia Beach expansion",
        "contact_phone": "+44 (0) 7795 900003",
        "contact_email": "enquiries@subseacraft.com",
        "contact_url": "https://subseacraft.com/contact/",
        "sources": [
            {"title": "SubSea Craft maritime technology", "url": "https://subseacraft.com/"},
            {
                "title": "SubSea Craft Virginia Beach expansion announcement",
                "url": "https://subseacraft.com/subsea-craft-kickstarts-u-s-expansion/",
            },
            {
                "title": "SubSea Craft U.S. recruitment and public contact information",
                "url": "https://subseacraft.com/contact/",
            },
        ],
        "provenance": "curated-public-source",
    },
    {
        "name": "Textron Systems Aerosonde UAS Center of Excellence",
        "record_type": "facility",
        "short_description": (
            "Blackstone center for Aerosonde UAS production, assembly, testing, training, "
            "operations, logistics, and sustainment."
        ),
        "overview": (
            "Textron Systems operates an Aerosonde UAS Center of Excellence in Blackstone. The "
            "company describes the 38,000-square-foot site as supporting production, assembly, "
            "flight testing, training, operations, logistics, and life-cycle support for its "
            "Aerosonde uncrewed aircraft family."
        ),
        "unmanned_systems_relevance": (
            "Provides documented Virginia manufacturing, integration, testing, training, "
            "operations, and sustainment capacity for Aerosonde uncrewed aircraft systems."
        ),
        "activity_status": "active",
        "current_activity": (
            "Textron's current operational-footprint directory lists the Blackstone site for "
            "air systems, operations and logistics support, and test, training, and simulation."
        ),
        "activity_source_url": ("https://www.textronsystems.com/our-company/operational-footprint"),
        "activity_last_verified_at": "2026-08-24",
        "address_line": "277 Dominy Corner Road",
        "city": "Blackstone",
        "state": "VA",
        "postal_code": "23824",
        "latitude": 37.082203,
        "longitude": -77.958505,
        "location_precision": "exact",
        "region": "Southside Virginia",
        "strategic_categories": [
            "Manufacturing and supply chain",
            "Test and operational environments",
            "Companies and solution providers",
            "Core unmanned-systems asset",
        ],
        "platform_domains": ["Unmanned aircraft systems"],
        "capabilities": [
            "Manufacturing, materials, and prototyping",
            "Testing, evaluation, verification, and validation",
            "Operations, maintenance, and sustainment",
            "Systems engineering and integration",
        ],
        "missions": ["ISR", "Training and experimentation", "Logistics and contested logistics"],
        "website_url": "https://www.textronsystems.com/products/aerosonde-uas",
        "contact_text": "Textron Systems Blackstone operation",
        "contact_phone": "434-298-0029",
        "contact_email": "",
        "contact_url": "https://www.textronsystems.com/our-company/operational-footprint",
        "sources": [
            {
                "title": "Textron Systems Blackstone operational footprint",
                "url": "https://www.textronsystems.com/our-company/operational-footprint",
            },
            {
                "title": "Textron Systems Aerosonde UAS",
                "url": "https://www.textronsystems.com/products/aerosonde-uas",
            },
            {
                "title": "Textron Aerosonde UAS Center of Excellence profile",
                "url": (
                    "https://www.textronsystems.com/our-company/news-events/articles/inside-ts/"
                    "aerosonde-uas-center-excellence"
                ),
            },
        ],
        "provenance": "curated-public-source",
    },
    {
        "name": "UVision USA Stafford Production and Training Center",
        "record_type": "facility",
        "short_description": (
            "Stafford production, assembly, training, and U.S. headquarters facility for "
            "UVision HERO loitering unmanned aircraft systems."
        ),
        "overview": (
            "UVision USA operates a 25,000-square-foot production and training center at the "
            "Quantico Corporate Center in Stafford. The company states that the facility "
            "produces the HERO family of loitering unmanned aircraft systems for U.S. and "
            "international customers."
        ),
        "unmanned_systems_relevance": (
            "Provides documented Virginia production, assembly, training, navigation, and "
            "payload-integration capacity for the HERO family of unmanned aircraft."
        ),
        "activity_status": "active",
        "current_activity": (
            "UVision's current U.S. page identifies the Stafford facility as an opened Virginia "
            "production site for HERO systems; state economic-development materials document "
            "its manufacturing and training purpose."
        ),
        "activity_source_url": "https://uvisionuav.com/uvision-usa/",
        "activity_last_verified_at": "2026-08-24",
        "address_line": "600 Corporate Drive",
        "city": "Stafford",
        "state": "VA",
        "postal_code": "22554",
        "latitude": 38.514916,
        "longitude": -77.366339,
        "location_precision": "exact",
        "region": "Fredericksburg Region",
        "strategic_categories": [
            "Manufacturing and supply chain",
            "Companies and solution providers",
            "Federal and defense customer access",
            "Core unmanned-systems asset",
        ],
        "platform_domains": ["Unmanned aircraft systems"],
        "capabilities": [
            "Manufacturing, materials, and prototyping",
            "Systems engineering and integration",
            "Payloads and mission systems",
            "Navigation and positioning",
        ],
        "missions": [
            "ISR",
            "Force protection and installation security",
            "Training and experimentation",
        ],
        "website_url": "https://uvisionuav.com/uvision-usa/",
        "contact_text": "UVision USA public contact",
        "contact_phone": "540-303-3354",
        "contact_email": "jim.truxel@uvisionusa.com",
        "contact_url": "https://uvisionuav.com/uvision-usa/",
        "sources": [
            {
                "title": "UVision USA Stafford production facility",
                "url": "https://uvisionuav.com/uvision-usa/",
            },
            {
                "title": "VEDP announcement of UVision Stafford production and training center",
                "url": (
                    "https://www.vedp.org/press-release/2021-12/"
                    "uvision-usa-corporation-stafford-county"
                ),
            },
            {
                "title": "UVision Stafford facility opening announcement",
                "url": "https://uvisionuav.com/wp-content/uploads/2023/06/UVision-USA-_Press-Release.pdf",
            },
        ],
        "provenance": "curated-public-source",
    },
    {
        "name": "ViDARR Virginia Beach Manufacturing Facility",
        "record_type": "facility",
        "short_description": (
            "Virginia Beach manufacturing facility producing modular UAS, autonomous systems, "
            "defense optics, and edge-manufactured components."
        ),
        "overview": (
            "ViDARR operates a 16,410-square-foot Virginia Beach manufacturing facility for "
            "advanced defense technologies, including autonomous systems, modular REAVERS "
            "uncrewed aircraft, thermal and night-vision payloads, and edge-manufactured "
            "components."
        ),
        "unmanned_systems_relevance": (
            "Provides documented Virginia production, assembly, component, payload, and "
            "integration capacity for modular uncrewed aircraft and related sensing systems."
        ),
        "activity_status": "active",
        "current_activity": (
            "ViDARR identifies the Virginia Beach address as its manufacturing facility and "
            "currently markets the modular REAVERS UAS and distributed-manufacturing approach."
        ),
        "activity_source_url": "https://vidarrinc.com/pages/reavers-home",
        "activity_last_verified_at": "2026-08-24",
        "address_line": "2656 Lishelle Place",
        "city": "Virginia Beach",
        "state": "VA",
        "postal_code": "23452",
        "latitude": 36.812091,
        "longitude": -76.067654,
        "location_precision": "exact",
        "region": "Hampton Roads",
        "strategic_categories": [
            "Manufacturing and supply chain",
            "Companies and solution providers",
            "Core unmanned-systems asset",
        ],
        "platform_domains": ["Unmanned aircraft systems"],
        "capabilities": [
            "Manufacturing, materials, and prototyping",
            "Payloads and mission systems",
            "Perception, sensing, and sensor fusion",
            "Systems engineering and integration",
        ],
        "missions": ["ISR", "Search and rescue", "Force protection and installation security"],
        "website_url": "https://vidarrinc.com/pages/about-us",
        "contact_text": "ViDARR Virginia Beach facility",
        "contact_phone": "877-636-8432",
        "contact_email": "peter@vidarrinc.com",
        "contact_url": "https://vidarrinc.com/pages/about-us",
        "sources": [
            {
                "title": "ViDARR Virginia Beach manufacturing facility",
                "url": "https://vidarrinc.com/pages/about-us",
            },
            {
                "title": "ViDARR REAVERS UAS and distributed manufacturing",
                "url": "https://vidarrinc.com/pages/reavers-home",
            },
            {
                "title": "VEDP announcement of ViDARR Virginia Beach manufacturing facility",
                "url": "https://www.vedp.org/press-release/2025-03/vidarr-inc-virginia-beach",
            },
        ],
        "provenance": "curated-public-source",
    },
]

# Second targeted expansion completed August 24. Records in this batch distinguish
# company-wide capabilities from what is documented at a particular Virginia site;
# announced facilities remain planned until a public source confirms operation.
VERIFIED_UXS_EXPANSION = [
    {
        "name": "Virtus Innovation Center",
        "record_type": "facility",
        "short_description": (
            "Arlington dual-use innovation center providing workspace, capital access, "
            "commercialization support, and government-market connections."
        ),
        "overview": (
            "Virtus Innovation Center is a membership-based, 16,000-plus-square-foot "
            "dual-use technology hub launched in June 2026 at 1550 Crystal Drive in "
            "Arlington. It supports early-stage national-security technology companies "
            "through workspace, programming, investor access, and commercialization paths."
        ),
        "unmanned_systems_relevance": (
            "Supports the wider dual-use company and investment ecosystem used by unmanned-"
            "systems ventures. Inclusion does not imply that every Virtus member works in UxS."
        ),
        "activity_status": "active",
        "current_activity": (
            "Virtus launched its Arlington center in June 2026 and currently accepts "
            "applications from dual-use founders, partners, investors, and government users."
        ),
        "activity_source_url": "https://www.virtusinnovation.com/",
        "activity_last_verified_at": "2026-08-24",
        "address_line": "1550 Crystal Drive, Suite 200",
        "city": "Arlington",
        "state": "VA",
        "postal_code": "22202",
        "latitude": 38.860251,
        "longitude": -77.049381,
        "location_precision": "exact",
        "region": "Northern Virginia",
        "strategic_categories": [
            "Commercialization and capital",
            "Companies and solution providers",
            "Federal and defense customer access",
            "Supporting ecosystem asset",
        ],
        "platform_domains": ["Cross-domain autonomy"],
        "capabilities": ["Systems engineering and integration"],
        "missions": ["Training and experimentation"],
        "website_url": "https://www.virtusinnovation.com/",
        "contact_text": "Virtus Innovation Center membership and partnership inquiries",
        "contact_phone": "",
        "contact_email": "MFellows@VirtusInnovation.com",
        "contact_url": "https://www.virtusinnovation.com/contact",
        "sources": [
            {
                "title": "Virtus Innovation Center facility and membership model",
                "url": "https://www.virtusinnovation.com/",
            },
            {
                "title": "Virtus Arlington address and public contact",
                "url": "https://www.virtusinnovation.com/contact",
            },
        ],
        "provenance": "curated-public-source",
    },
    {
        "name": "Magothy River Technologies",
        "record_type": "organization",
        "short_description": (
            "Herndon marine-autonomy company developing autopilots and control systems for "
            "unmanned surface, undersea, remotely operated, and hybrid vehicles."
        ),
        "overview": (
            "Magothy River Technologies is a Herndon-based marine-autonomy company. Its "
            "published products and services include professional autopilots, navigation, "
            "path planning, radar processing, obstacle avoidance, simulation, and integration "
            "for USVs, UUVs, ROVs, towed systems, and hybrid marine vehicles."
        ),
        "unmanned_systems_relevance": (
            "Develops direct autonomy, navigation, control, and perception technology for "
            "uncrewed maritime platforms."
        ),
        "activity_status": "active",
        "current_activity": (
            "The company currently markets its Magothy Autopilot and engineering services for "
            "USV, UUV, ROV, and collaborative marine-autonomy applications."
        ),
        "activity_source_url": "https://www.magothyrt.com/autopilot",
        "activity_last_verified_at": "2026-08-24",
        "city": "Herndon",
        "state": "VA",
        "postal_code": "",
        "latitude": 38.9696,
        "longitude": -77.3861,
        "location_precision": "locality",
        "region": "Northern Virginia",
        "strategic_categories": [
            "Companies and solution providers",
            "Research and technical depth",
            "Core unmanned-systems asset",
        ],
        "platform_domains": ["Maritime surface systems", "Undersea systems"],
        "capabilities": [
            "Autonomy and artificial intelligence",
            "Navigation and positioning",
            "Perception, sensing, and sensor fusion",
            "Systems engineering and integration",
        ],
        "missions": ["Maritime domain awareness", "ISR", "Surveying and mapping"],
        "website_url": "https://www.magothyrt.com/",
        "contact_text": "Magothy River Technologies company inquiries",
        "contact_phone": "703-791-9632",
        "contact_email": "info@magothyrt.com",
        "contact_url": "https://www.magothyrt.com/contact",
        "sources": [
            {
                "title": "Magothy River Technologies marine-autonomy capabilities",
                "url": "https://www.magothyrt.com/",
            },
            {
                "title": "Magothy Autopilot product details",
                "url": "https://www.magothyrt.com/autopilot",
            },
            {
                "title": "Magothy River Technologies Herndon contact information",
                "url": "https://www.magothyrt.com/contact",
            },
        ],
        "provenance": "curated-public-source",
    },
    {
        "name": "TurbineOne Headquarters and T1 Edgeworks",
        "record_type": "facility",
        "short_description": (
            "Announced Chantilly headquarters and R&D experience lab for edge AI used in "
            "autonomous and semi-autonomous defense missions."
        ),
        "overview": (
            "TurbineOne announced in May 2026 that it would establish its headquarters in "
            "Fairfax County and create T1 Edgeworks, an R&D experience lab in Chantilly. "
            "Public company and Commonwealth sources describe edge AI for threat detection, "
            "team decision support, and orchestration of autonomous or semi-autonomous missions."
        ),
        "unmanned_systems_relevance": (
            "Develops edge AI with documented UAS and autonomous-mission applications; the "
            "Virginia headquarters and lab remain an announced project until opening is confirmed."
        ),
        "activity_status": "planned",
        "current_activity": (
            "The Commonwealth and TurbineOne announced the Fairfax County headquarters and "
            "Chantilly T1 Edgeworks project in May 2026. No public street address or opening "
            "confirmation was located during this review."
        ),
        "activity_source_url": (
            "https://www.governor.virginia.gov/newsroom/news-releases/2026/"
            "may-releases/name-1117183-en.html"
        ),
        "activity_last_verified_at": "2026-08-24",
        "city": "Chantilly",
        "state": "VA",
        "postal_code": "",
        "latitude": 38.875,
        "longitude": -77.442,
        "location_precision": "locality",
        "region": "Northern Virginia",
        "strategic_categories": [
            "Companies and solution providers",
            "Research and technical depth",
            "Federal and defense customer access",
            "Core unmanned-systems asset",
        ],
        "platform_domains": [
            "Unmanned aircraft systems",
            "Ground vehicles and robotics",
            "Cross-domain autonomy",
        ],
        "capabilities": [
            "Autonomy and artificial intelligence",
            "Data engineering, analytics, and edge computing",
            "Payloads and mission systems",
            "Systems engineering and integration",
        ],
        "missions": ["ISR", "Force protection and installation security"],
        "website_url": "https://www.turbineone.com/company/newsroom",
        "contact_text": "TurbineOne public contact listed in the Virginia project announcement",
        "contact_phone": "",
        "contact_email": "jamie@turbineone.com",
        "contact_url": (
            "https://www.governor.virginia.gov/newsroom/news-releases/2026/"
            "may-releases/name-1117183-en.html"
        ),
        "sources": [
            {
                "title": "TurbineOne newsroom and Edgeworks announcement",
                "url": "https://www.turbineone.com/company/newsroom",
            },
            {
                "title": "Virginia announcement of TurbineOne headquarters and T1 Edgeworks",
                "url": (
                    "https://www.governor.virginia.gov/newsroom/news-releases/2026/"
                    "may-releases/name-1117183-en.html"
                ),
            },
            {
                "title": "Federal SBIR award for TurbineOne AutoML for UAS",
                "url": "https://www.sbir.gov/awards/194997",
            },
        ],
        "provenance": "curated-public-source",
    },
    {
        "name": "AURA Network Systems",
        "record_type": "organization",
        "short_description": (
            "McLean aviation-communications company providing licensed spectrum, radios, and "
            "network infrastructure for UAS command and control and BVLOS operations."
        ),
        "overview": (
            "AURA Network Systems is headquartered in McLean and develops aviation-dedicated "
            "communications infrastructure. Its public materials describe licensed spectrum, "
            "airborne radios, ground systems, and deterministic frequency allocation for "
            "uncrewed-aircraft command and control, including BVLOS routes."
        ),
        "unmanned_systems_relevance": (
            "Provides direct communications and spectrum infrastructure intended to support "
            "safe UAS command-and-control links and integration into national airspace."
        ),
        "activity_status": "active",
        "current_activity": (
            "AURA currently offers airborne radios for aircraft integration and ground systems "
            "for test flights while advancing standards and services for UAS C2 links."
        ),
        "activity_source_url": "https://auranetworksystems.com/infrastructure",
        "activity_last_verified_at": "2026-08-24",
        "address_line": "1765 Greensboro Station Place, 9th Floor",
        "city": "McLean",
        "state": "VA",
        "postal_code": "22102",
        "latitude": 38.922148,
        "longitude": -77.233232,
        "location_precision": "exact",
        "region": "Northern Virginia",
        "strategic_categories": [
            "Companies and solution providers",
            "Physical infrastructure and logistics",
            "Research and technical depth",
            "Core unmanned-systems asset",
        ],
        "platform_domains": ["Unmanned aircraft systems", "Advanced Air Mobility"],
        "capabilities": [
            "Command, control, and communications",
            "Safety, policy, regulatory, and airspace integration",
            "Systems engineering and integration",
        ],
        "missions": ["Communications relay", "Logistics and contested logistics"],
        "website_url": "https://auranetworksystems.com/infrastructure",
        "contact_text": "AURA Network Systems public inquiry form",
        "contact_phone": "",
        "contact_email": "",
        "contact_url": "https://auranetworksystems.com/contact",
        "sources": [
            {
                "title": "AURA UAS communications infrastructure",
                "url": "https://auranetworksystems.com/infrastructure",
            },
            {
                "title": "AURA McLean headquarters",
                "url": "https://auranetworksystems.com/company",
            },
            {
                "title": "AURA public contact route",
                "url": "https://auranetworksystems.com/contact",
            },
        ],
        "provenance": "curated-public-source",
    },
    {
        "name": "TruWeather Solutions",
        "record_type": "organization",
        "short_description": (
            "Reston aviation-weather company providing hyperlocal data, sensors, forecasting, "
            "and decision tools for drones, AAM, public safety, and BVLOS operations."
        ),
        "overview": (
            "TruWeather Solutions identifies Reston as its Virginia and Washington-area "
            "headquarters. It combines aviation-weather software, ground sensors, micro-weather "
            "stations, forecasting, and regulatory support for drone and advanced-air-mobility "
            "operations."
        ),
        "unmanned_systems_relevance": (
            "Provides purpose-built low-altitude weather intelligence and go/no-go decision "
            "support for UAS, autonomous aerial missions, public safety, and BVLOS operations."
        ),
        "activity_status": "active",
        "current_activity": (
            "TruWeather currently markets its V360 weather platform, infrastructure, and "
            "professional services for drone pilots, air taxis, and autonomous aerial missions."
        ),
        "activity_source_url": "https://truweathersolutions.com/",
        "activity_last_verified_at": "2026-08-24",
        "city": "Reston",
        "state": "VA",
        "postal_code": "",
        "latitude": 38.959,
        "longitude": -77.357,
        "location_precision": "locality",
        "region": "Northern Virginia",
        "strategic_categories": [
            "Companies and solution providers",
            "Research and technical depth",
            "Core unmanned-systems asset",
        ],
        "platform_domains": ["Unmanned aircraft systems", "Advanced Air Mobility"],
        "capabilities": [
            "Data engineering, analytics, and edge computing",
            "Perception, sensing, and sensor fusion",
            "Safety, policy, regulatory, and airspace integration",
        ],
        "missions": [
            "Public safety and emergency response",
            "Environmental monitoring",
            "Logistics and contested logistics",
        ],
        "website_url": "https://truweathersolutions.com/",
        "contact_text": "TruWeather Solutions general inquiries",
        "contact_phone": "877-633-9911",
        "contact_email": "info@truweathersolutions.com",
        "contact_url": "https://truweathersolutions.com/",
        "sources": [
            {
                "title": "TruWeather aviation-weather products and Reston headquarters",
                "url": "https://truweathersolutions.com/",
            },
            {
                "title": "TruWeather public-safety and BVLOS weather applications",
                "url": "https://truweathersolutions.com/public-safety/",
            },
        ],
        "provenance": "curated-public-source",
    },
    {
        "name": "Advanced Technology Systems Company DroneSting",
        "record_type": "organization",
        "short_description": (
            "McLean defense company developing the DroneSting family of modular fixed, mobile, "
            "and wearable counter-UAS detection and defeat systems."
        ),
        "overview": (
            "Advanced Technology Systems Company (ATSC) is headquartered in McLean. Its "
            "DroneSting counter-UAS family combines RF sensing, radar, electro-optical and "
            "infrared cameras, AI-assisted recognition, command and control, and multiple "
            "mitigation options for fixed, mobile, and expeditionary use."
        ),
        "unmanned_systems_relevance": (
            "Develops direct counter-UAS sensing, tracking, command-and-control, and defeat "
            "capabilities."
        ),
        "activity_status": "active",
        "current_activity": (
            "ATSC currently markets the DroneSting family, including the wearable Scout system, "
            "and reported a live full kill-chain demonstration of the product family in 2025."
        ),
        "activity_source_url": "https://www.atscva.com/dronesting-scout/",
        "activity_last_verified_at": "2026-08-24",
        "address_line": "2010 Corporate Ridge Drive, Suite 910",
        "city": "McLean",
        "state": "VA",
        "postal_code": "22102",
        "latitude": 38.912931,
        "longitude": -77.217102,
        "location_precision": "exact",
        "region": "Northern Virginia",
        "strategic_categories": [
            "Companies and solution providers",
            "Federal and defense customer access",
            "Core unmanned-systems asset",
        ],
        "platform_domains": ["Counter-UAS"],
        "capabilities": [
            "Perception, sensing, and sensor fusion",
            "Command, control, and communications",
            "Autonomy and artificial intelligence",
            "Systems engineering and integration",
        ],
        "missions": ["Counter-UAS", "Force protection and installation security"],
        "website_url": "https://www.atscva.com/",
        "contact_text": "ATSC headquarters inquiries",
        "contact_phone": "703-556-0557",
        "contact_email": "info@atscva.com",
        "contact_url": "https://www.atscva.com/",
        "sources": [
            {
                "title": "ATSC DroneSting counter-UAS family and headquarters",
                "url": "https://www.atscva.com/",
            },
            {
                "title": "ATSC DroneSting Scout product profile",
                "url": "https://www.atscva.com/dronesting-scout/",
            },
        ],
        "provenance": "curated-public-source",
    },
    {
        "name": "D-Fend Solutions North American Headquarters",
        "record_type": "organization",
        "short_description": (
            "McLean North American headquarters for EnforceAir cyber and RF-based counter-drone "
            "detection, identification, and controlled-takeover technology."
        ),
        "overview": (
            "D-Fend Solutions operates its North American headquarters in McLean. Its EnforceAir "
            "system detects, identifies, and mitigates unauthorized drones through RF cyber "
            "takeover intended to support a controlled landing rather than jamming or kinetic defeat."
        ),
        "unmanned_systems_relevance": (
            "Provides direct counter-UAS detection and mitigation technology and North American "
            "sales, demonstrations, delivery, support, and maintenance from Virginia."
        ),
        "activity_status": "active",
        "current_activity": (
            "D-Fend continues to market and support EnforceAir after Motorola Solutions completed "
            "its acquisition of D-Fend Solutions in August 2026."
        ),
        "activity_source_url": "https://d-fendsolutions.com/",
        "activity_last_verified_at": "2026-08-24",
        "address_line": "1640 Boro Place, 4th Floor",
        "city": "McLean",
        "state": "VA",
        "postal_code": "22102",
        "latitude": 38.924472,
        "longitude": -77.233497,
        "location_precision": "exact",
        "region": "Northern Virginia",
        "strategic_categories": [
            "Companies and solution providers",
            "Federal and defense customer access",
            "Core unmanned-systems asset",
        ],
        "platform_domains": ["Counter-UAS"],
        "capabilities": [
            "Perception, sensing, and sensor fusion",
            "Command, control, and communications",
            "Systems engineering and integration",
        ],
        "missions": ["Counter-UAS", "Force protection and installation security"],
        "website_url": "https://d-fendsolutions.com/",
        "contact_text": "D-Fend North American office listing",
        "contact_phone": "240-786-8513",
        "contact_email": "",
        "contact_url": "https://www.navair.navy.mil/osbp/node/10916",
        "sources": [
            {
                "title": "D-Fend EnforceAir counter-drone technology",
                "url": "https://d-fendsolutions.com/",
            },
            {
                "title": "D-Fend North American headquarters expansion",
                "url": (
                    "https://d-fendsolutions.com/press_releases/"
                    "d-fend-solutions-significantly-expands-operations-in-north-america-"
                    "to-meet-increasing-demand-for-its-counter-drone-solutions/"
                ),
            },
            {
                "title": "NAVAIR D-Fend McLean company profile",
                "url": "https://www.navair.navy.mil/osbp/node/10916",
            },
        ],
        "provenance": "curated-public-source",
    },
    {
        "name": "SAIC Counter-UAS Integration",
        "record_type": "organization",
        "short_description": (
            "Reston-headquartered systems integrator providing configurable counter-UAS design, "
            "sensor and effector integration, testing, training, deployment, and sustainment."
        ),
        "overview": (
            "SAIC is headquartered in Reston and publishes a dedicated counter-UAS capability. "
            "Its offering covers architecture and design, sensors and effectors, command and "
            "control, testing, training, field integration, logistics, and long-term sustainment."
        ),
        "unmanned_systems_relevance": (
            "Provides direct counter-UAS systems integration and lifecycle support for fixed, "
            "mobile, tactical, airport, border, and infrastructure missions."
        ),
        "activity_status": "active",
        "current_activity": (
            "SAIC currently markets full-spectrum counter-UAS integration covering detection, "
            "tracking, mitigation, data analysis, testing, training, fielding, and sustainment."
        ),
        "activity_source_url": "https://experience.saic.com/cuas",
        "activity_last_verified_at": "2026-08-24",
        "address_line": "12010 Sunset Hills Road",
        "city": "Reston",
        "state": "VA",
        "postal_code": "20190",
        "latitude": 38.955451,
        "longitude": -77.356423,
        "location_precision": "exact",
        "region": "Northern Virginia",
        "strategic_categories": [
            "Companies and solution providers",
            "Federal and defense customer access",
            "Core unmanned-systems asset",
        ],
        "platform_domains": ["Counter-UAS"],
        "capabilities": [
            "Systems engineering and integration",
            "Perception, sensing, and sensor fusion",
            "Command, control, and communications",
            "Testing, evaluation, verification, and validation",
            "Operations, maintenance, and sustainment",
        ],
        "missions": ["Counter-UAS", "Force protection and installation security"],
        "website_url": "https://experience.saic.com/cuas",
        "contact_text": "SAIC solutions and services inquiries",
        "contact_phone": "",
        "contact_email": "info@SAIC.io",
        "contact_url": "https://www.saic.com/contact-us",
        "sources": [
            {
                "title": "SAIC counter-UAS integration capability",
                "url": "https://experience.saic.com/cuas",
            },
            {
                "title": "SAIC Reston headquarters and public contact route",
                "url": "https://www.saic.com/contact-us",
            },
        ],
        "provenance": "curated-public-source",
    },
    {
        "name": "DCS Corporation",
        "record_type": "organization",
        "short_description": (
            "Alexandria-headquartered engineering company supporting unmanned air, ground, and "
            "undersea command and control, autonomous sensing, prototyping, simulation, and test."
        ),
        "overview": (
            "DCS Corporation is headquartered in Alexandria. Its public capability materials "
            "describe command and control for unmanned air, ground, and undersea systems, "
            "collaborative autonomous sensing, manned-unmanned teaming, rapid prototyping, "
            "modeling and simulation, and test and evaluation."
        ),
        "unmanned_systems_relevance": (
            "Provides direct engineering and integration capabilities for multi-domain unmanned "
            "systems, autonomy, sensing, mission planning, and C5ISR."
        ),
        "activity_status": "active",
        "current_activity": (
            "DCS currently lists unmanned systems and manned-unmanned teaming among its mission "
            "capabilities and documents active command-and-control and autonomous-sensing work."
        ),
        "activity_source_url": "https://www.dcscorp.com/home/what-we-do/c5isr/",
        "activity_last_verified_at": "2026-08-24",
        "address_line": "6909 Metro Park Drive, Suite 500",
        "city": "Alexandria",
        "state": "VA",
        "postal_code": "22310",
        "latitude": 38.769243,
        "longitude": -77.156538,
        "location_precision": "exact",
        "region": "Northern Virginia",
        "strategic_categories": [
            "Companies and solution providers",
            "Research and technical depth",
            "Federal and defense customer access",
            "Core unmanned-systems asset",
        ],
        "platform_domains": [
            "Unmanned aircraft systems",
            "Ground vehicles and robotics",
            "Undersea systems",
            "Cross-domain autonomy",
        ],
        "capabilities": [
            "Command, control, and communications",
            "Autonomy and artificial intelligence",
            "Perception, sensing, and sensor fusion",
            "Simulation, digital twins, and synthetic environments",
            "Testing, evaluation, verification, and validation",
        ],
        "missions": ["ISR", "Training and experimentation"],
        "website_url": "https://dcscorp.com/",
        "contact_text": "DCS Corporation headquarters inquiries",
        "contact_phone": "571-227-6000",
        "contact_email": "info@dcscorp.com",
        "contact_url": "https://dcscorp.com/",
        "sources": [
            {
                "title": "DCS unmanned-systems capabilities and Alexandria headquarters",
                "url": "https://dcscorp.com/",
            },
            {
                "title": "DCS C5ISR and unmanned-system command-and-control capabilities",
                "url": "https://www.dcscorp.com/home/what-we-do/c5isr/",
            },
        ],
        "provenance": "curated-public-source",
    },
    {
        "name": "Trident Systems Chantilly Production Facility",
        "record_type": "facility",
        "short_description": (
            "Documented Chantilly production facility within a defense-electronics company whose "
            "portfolio includes mobile counter-UAS surveillance and tracking systems."
        ),
        "overview": (
            "Trident Systems lists a production facility in Chantilly. The company's public "
            "portfolio includes C4ISR systems and a Mobile Security Surveillance System with a "
            "counter-UAS variant, but available sources do not identify which products are "
            "manufactured at the Chantilly address."
        ),
        "unmanned_systems_relevance": (
            "Represents documented Virginia production capacity within a company that supplies "
            "counter-UAS and C4ISR products; it is classified as supporting because the public "
            "record does not tie a specific UxS production line to this site."
        ),
        "activity_status": "active",
        "current_activity": (
            "Trident currently lists the Chantilly address as its Virginia production facility. "
            "Its published MS3 product sheet documents a counter-UAS variant without assigning "
            "that product to a particular manufacturing location."
        ),
        "activity_source_url": "https://tridsys.com/contact-us/",
        "activity_last_verified_at": "2026-08-24",
        "address_line": "3810 Concorde Parkway, Suite 2200",
        "city": "Chantilly",
        "state": "VA",
        "postal_code": "20151",
        "latitude": 38.910668,
        "longitude": -77.450446,
        "location_precision": "exact",
        "region": "Northern Virginia",
        "strategic_categories": [
            "Manufacturing and supply chain",
            "Federal and defense customer access",
            "Supporting ecosystem asset",
        ],
        "platform_domains": ["Counter-UAS"],
        "capabilities": [
            "Manufacturing, materials, and prototyping",
            "Systems engineering and integration",
            "Perception, sensing, and sensor fusion",
        ],
        "missions": ["Counter-UAS", "Force protection and installation security"],
        "website_url": "https://tridsys.com/contact-us/",
        "contact_text": "Trident Systems general and C4ISR product inquiries",
        "contact_phone": "703-273-1012",
        "contact_email": "info@tridsys.com",
        "contact_url": "https://tridsys.com/contact-us/",
        "sources": [
            {
                "title": "Trident Systems Chantilly production facility",
                "url": "https://tridsys.com/contact-us/",
            },
            {
                "title": "Trident MS3 counter-UAS variant product sheet",
                "url": "https://tridsys.com/wp-content/uploads/2024/04/MS3-Cutsheet.pdf",
            },
        ],
        "provenance": "curated-public-source",
    },
    {
        "name": "WNK Aviation",
        "record_type": "organization",
        "short_description": (
            "Arlington UAS and counter-UAS integrator providing technology sourcing, mission "
            "integration, training, electronic-warfare support, and capacity building."
        ),
        "overview": (
            "WNK Aviation is an Arlington-based, service-disabled veteran-owned company focused "
            "on UAS and counter-UAS solutions. Its public capability pages describe drone and "
            "counter-drone technology sourcing, integration, advisory services, training, "
            "electronic-warfare support, and partner-nation capacity building."
        ),
        "unmanned_systems_relevance": (
            "Provides direct UAS and counter-UAS integration, procurement support, training, "
            "and mission-advisory services."
        ),
        "activity_status": "active",
        "current_activity": (
            "WNK currently presents UAS, counter-UAS, electronic-warfare, training, integration, "
            "and capacity-building services from its Arlington office. These capability claims "
            "are company-published and have not been independently performance-tested by COSOLVE."
        ),
        "activity_source_url": "https://www.wnkaviation.com/capabilities",
        "activity_last_verified_at": "2026-08-24",
        "address_line": "1101 Wilson Boulevard, Floor 6",
        "city": "Arlington",
        "state": "VA",
        "postal_code": "22209",
        "latitude": 38.894767,
        "longitude": -77.069545,
        "location_precision": "exact",
        "region": "Northern Virginia",
        "strategic_categories": [
            "Companies and solution providers",
            "Federal and defense customer access",
            "Core unmanned-systems asset",
        ],
        "platform_domains": ["Unmanned aircraft systems", "Counter-UAS"],
        "capabilities": [
            "Systems engineering and integration",
            "Operations, maintenance, and sustainment",
            "Command, control, and communications",
        ],
        "missions": [
            "Counter-UAS",
            "Training and experimentation",
            "Force protection and installation security",
        ],
        "website_url": "https://www.wnkaviation.com/",
        "contact_text": "WNK Aviation company inquiries",
        "contact_phone": "757-752-8421",
        "contact_email": "wnkaviation@proton.me",
        "contact_url": "https://www.wnkaviation.com/about-4",
        "sources": [
            {
                "title": "WNK Aviation UAS and counter-UAS company profile",
                "url": "https://www.wnkaviation.com/",
            },
            {
                "title": "WNK Aviation capabilities",
                "url": "https://www.wnkaviation.com/capabilities",
            },
            {
                "title": "WNK Aviation Arlington address and contact information",
                "url": "https://www.wnkaviation.com/about-4",
            },
        ],
        "provenance": "curated-public-source",
    },
    {
        "name": "H2P Solution",
        "record_type": "organization",
        "short_description": (
            "Fairfax counter-UAS training and readiness company serving defense, intelligence, "
            "public-safety, and allied organizations."
        ),
        "overview": (
            "H2P Solution is a Fairfax-based, service-disabled veteran-owned small business "
            "focused on counter-UAS readiness. Its services cover threat and capability "
            "assessment, planning, leadership education, operator training, tabletop and field "
            "exercises, program development, and periodic reassessment."
        ),
        "unmanned_systems_relevance": (
            "Provides direct counter-UAS workforce, planning, exercise, assessment, and "
            "operational-readiness support."
        ),
        "activity_status": "active",
        "current_activity": (
            "H2P currently offers counter-UAS training, readiness assessments, exercises, and "
            "program-development support from Fairfax."
        ),
        "activity_source_url": "https://www.h2psolution.com/services/",
        "activity_last_verified_at": "2026-08-24",
        "city": "Fairfax",
        "state": "VA",
        "postal_code": "",
        "latitude": 38.846,
        "longitude": -77.307,
        "location_precision": "locality",
        "region": "Northern Virginia",
        "strategic_categories": [
            "Companies and solution providers",
            "Workforce and talent",
            "Federal and defense customer access",
            "Core unmanned-systems asset",
        ],
        "platform_domains": ["Counter-UAS"],
        "capabilities": [
            "Testing, evaluation, verification, and validation",
            "Operations, maintenance, and sustainment",
            "Safety, policy, regulatory, and airspace integration",
        ],
        "missions": [
            "Counter-UAS",
            "Training and experimentation",
            "Force protection and installation security",
        ],
        "website_url": "https://www.h2psolution.com/",
        "contact_text": "H2P Solution consultation inquiries",
        "contact_phone": "571-605-9578",
        "contact_email": "admin@h2psolution.com",
        "contact_url": "https://www.h2psolution.com/",
        "sources": [
            {
                "title": "H2P counter-UAS training and readiness profile",
                "url": "https://www.h2psolution.com/",
            },
            {
                "title": "H2P counter-UAS services",
                "url": "https://www.h2psolution.com/services/",
            },
            {
                "title": "H2P Fairfax company background",
                "url": "https://www.h2psolution.com/about/",
            },
        ],
        "provenance": "curated-public-source",
    },
    {
        "name": "BZRD Systems",
        "record_type": "organization",
        "short_description": (
            "Blacksburg startup developing passive, AI-assisted UAS detection and tracking "
            "designed to share threat tracks through ATAK without emitting an RF signature."
        ),
        "overview": (
            "BZRD Systems is a Blacksburg startup originating from Virginia Tech's Hacking for "
            "Defense program. The company describes a developing passive counter-UAS awareness "
            "system using onboard AI to classify and track drone signals and publish detections "
            "into ATAK mission workflows."
        ),
        "unmanned_systems_relevance": (
            "Develops direct passive counter-UAS sensing, AI classification, tracking, and "
            "tactical common-operating-picture integration."
        ),
        "activity_status": "developing",
        "current_activity": (
            "BZRD launched its public site in July 2026 and describes its system as a developing "
            "capability moving from prototype and field validation toward deployment. The record "
            "does not present the product as broadly fielded."
        ),
        "activity_source_url": "https://www.bzrdsystems.com/",
        "activity_last_verified_at": "2026-08-24",
        "city": "Blacksburg",
        "state": "VA",
        "postal_code": "24060",
        "latitude": 37.229,
        "longitude": -80.414,
        "location_precision": "locality",
        "region": "New River Valley",
        "strategic_categories": [
            "Companies and solution providers",
            "Research and technical depth",
            "Core unmanned-systems asset",
        ],
        "platform_domains": ["Counter-UAS"],
        "capabilities": [
            "Perception, sensing, and sensor fusion",
            "Autonomy and artificial intelligence",
            "Command, control, and communications",
            "Data engineering, analytics, and edge computing",
        ],
        "missions": ["Counter-UAS", "Force protection and installation security"],
        "website_url": "https://www.bzrdsystems.com/",
        "contact_text": "BZRD Systems public contact form",
        "contact_phone": "",
        "contact_email": "",
        "contact_url": "https://www.bzrdsystems.com/",
        "sources": [
            {
                "title": "BZRD Systems passive counter-UAS technology and contact route",
                "url": "https://www.bzrdsystems.com/",
            },
            {
                "title": "BZRD Systems official company profile and Blacksburg location",
                "url": "https://www.linkedin.com/company/bzrd-systems",
            },
        ],
        "provenance": "curated-public-source",
    },
    {
        "name": "GoTAK",
        "record_type": "organization",
        "short_description": (
            "Virginia Beach tactical-communications integrator supporting UAS tracking, "
            "counter-UAS sensors, RF payloads, TAK software, provisioning, and sustainment."
        ),
        "overview": (
            "GoTAK is a Virginia Beach engineering and systems-integration company built around "
            "the Team Awareness Kit ecosystem. Its public profile documents RF, counter-UAS, "
            "tracking, and RIDAR drone-detection payloads, mission software, plugins, equipment "
            "provisioning, deployment, and sustainment."
        ),
        "unmanned_systems_relevance": (
            "Integrates UAS tracking and counter-UAS sensor data into tactical command-and-control "
            "workflows and supports field deployment from Virginia Beach."
        ),
        "activity_status": "active",
        "current_activity": (
            "GoTAK currently engineers and supports UAS trackers, drone-detection integrations, "
            "RF tools, TAK software, and deployment packages from Virginia Beach."
        ),
        "activity_source_url": "https://getgotak.com/pages/forge",
        "activity_last_verified_at": "2026-08-24",
        "address_line": "780 Lynnhaven Parkway, Suite 400",
        "city": "Virginia Beach",
        "state": "VA",
        "postal_code": "23452",
        "latitude": 36.815503,
        "longitude": -76.06677,
        "location_precision": "exact",
        "region": "Hampton Roads",
        "strategic_categories": [
            "Companies and solution providers",
            "Federal and defense customer access",
            "Core unmanned-systems asset",
        ],
        "platform_domains": ["Unmanned aircraft systems", "Counter-UAS"],
        "capabilities": [
            "Command, control, and communications",
            "Systems engineering and integration",
            "Payloads and mission systems",
            "Operations, maintenance, and sustainment",
        ],
        "missions": [
            "Counter-UAS",
            "ISR",
            "Public safety and emergency response",
        ],
        "website_url": "https://getgotak.com/pages/about-us",
        "contact_text": "GoTAK sales and integration inquiries",
        "contact_phone": "757-910-0259",
        "contact_email": "sales@getgotak.com",
        "contact_url": "https://getgotak.com/pages/about-us",
        "sources": [
            {
                "title": "GoTAK company, sensor, UAS, and contact profile",
                "url": "https://getgotak.com/pages/about-us",
            },
            {
                "title": "GoTAK FORGE UAS tracking and integration capabilities",
                "url": "https://getgotak.com/pages/forge",
            },
        ],
        "provenance": "curated-public-source",
    },
    {
        "name": "DroneTrace",
        "record_type": "organization",
        "short_description": (
            "Charlottesville-area company providing AI-assisted field exploitation of captured "
            "air, land, and maritime unmanned systems."
        ),
        "overview": (
            "DroneTrace is a service-disabled veteran-owned small business located near "
            "Charlottesville. Its web-based platform and services are designed to extract flight "
            "paths, telemetry, command-and-control configurations, payload activity, media, "
            "mission logs, and network information from captured unmanned systems."
        ),
        "unmanned_systems_relevance": (
            "Provides direct UxS exploitation, reverse engineering, signature analysis, training, "
            "and intelligence-workflow support across aerial, ground, and maritime platforms."
        ),
        "activity_status": "active",
        "current_activity": (
            "DroneTrace currently offers platform demonstrations, user certification, field "
            "deployment support, custom exploitation modules, and UxS exploitation training."
        ),
        "activity_source_url": "https://www.dronetrace.com/capabilities",
        "activity_last_verified_at": "2026-08-24",
        "city": "Charlottesville",
        "state": "VA",
        "postal_code": "",
        "latitude": 38.035,
        "longitude": -78.503,
        "location_precision": "locality",
        "region": "Central Virginia",
        "strategic_categories": [
            "Companies and solution providers",
            "Federal and defense customer access",
            "Core unmanned-systems asset",
        ],
        "platform_domains": [
            "Unmanned aircraft systems",
            "Ground vehicles and robotics",
            "Maritime surface systems",
            "Undersea systems",
        ],
        "capabilities": [
            "Data engineering, analytics, and edge computing",
            "Autonomy and artificial intelligence",
            "Testing, evaluation, verification, and validation",
            "Payloads and mission systems",
        ],
        "missions": ["ISR", "Counter-UAS", "Training and experimentation"],
        "website_url": "https://www.dronetrace.com/home",
        "contact_text": "DroneTrace company inquiries",
        "contact_phone": "",
        "contact_email": "Info@dronetrace.com",
        "contact_url": "https://www.dronetrace.com/contact",
        "sources": [
            {
                "title": "DroneTrace platform, company, and Virginia location",
                "url": "https://www.dronetrace.com/home",
            },
            {
                "title": "DroneTrace UxS exploitation capabilities",
                "url": "https://www.dronetrace.com/capabilities",
            },
            {
                "title": "DroneTrace public contact route",
                "url": "https://www.dronetrace.com/contact",
            },
        ],
        "provenance": "curated-public-source",
    },
    {
        "name": "SRC Herndon RF and Systems Engineering Lab",
        "record_type": "facility",
        "short_description": (
            "Herndon RF and systems-engineering office within a company that develops radar, "
            "electronic-warfare, direction-finding, and counter-UAS technology."
        ),
        "overview": (
            "SRC's Herndon office includes more than 16,000 square feet of office and static-safe "
            "laboratory space for development and testing of radio-electronic circuits, devices, "
            "and systems. SRC separately documents counter-UAS radar, direction finding, spectrum "
            "sensing, and electronic-warfare products."
        ),
        "unmanned_systems_relevance": (
            "Provides a Virginia RF and systems-engineering lab inside a direct counter-UAS "
            "technology company. It is classified as supporting because public sources do not "
            "assign a specific counter-UAS product line to the Herndon office."
        ),
        "activity_status": "active",
        "current_activity": (
            "SRC currently lists the Herndon office and RF laboratory as active and continues to "
            "market passive direction-finding and counter-UAS spectrum-sensing systems."
        ),
        "activity_source_url": "https://www.srcinc.com/about/locations/herndon-va.html",
        "activity_last_verified_at": "2026-08-24",
        "address_line": "13861 Sunrise Valley Drive, Building 1, Suite 450",
        "city": "Herndon",
        "state": "VA",
        "postal_code": "20171",
        "latitude": 38.949669,
        "longitude": -77.422129,
        "location_precision": "exact",
        "region": "Northern Virginia",
        "strategic_categories": [
            "Research and technical depth",
            "Federal and defense customer access",
            "Supporting ecosystem asset",
        ],
        "platform_domains": ["Counter-UAS"],
        "capabilities": [
            "Perception, sensing, and sensor fusion",
            "Testing, evaluation, verification, and validation",
            "Systems engineering and integration",
            "Command, control, and communications",
        ],
        "missions": ["Counter-UAS", "Force protection and installation security"],
        "website_url": "https://www.srcinc.com/about/locations/herndon-va.html",
        "contact_text": "SRC Herndon office",
        "contact_phone": "703-961-5500",
        "contact_email": "",
        "contact_url": "https://www.srcinc.com/about/locations/herndon-va.html",
        "sources": [
            {
                "title": "SRC Herndon office and RF laboratory",
                "url": "https://www.srcinc.com/about/locations/herndon-va.html",
            },
            {
                "title": "SRC counter-UAS direction-finding systems",
                "url": (
                    "https://www.srcinc.com/products/ew-spectrum-operations/"
                    "direction-finding-systems.html"
                ),
            },
        ],
        "provenance": "curated-public-source",
    },
    {
        "name": "Marine Sonic Technology",
        "record_type": "organization",
        "short_description": (
            "Yorktown sonar company supplying embedded side-scan and synthetic-aperture systems "
            "for autonomous underwater vehicles, remotely operated vehicles, and towed platforms."
        ),
        "overview": (
            "Marine Sonic Technology operates from Yorktown as a TKMS ATLAS North America brand. "
            "It develops and supplies side-scan sonar, synthetic-aperture sonar, collision-"
            "avoidance sonar, depth sounders, and embedded systems for AUV, ROV, and towed use."
        ),
        "unmanned_systems_relevance": (
            "Provides Virginia-based sonar products, integration interfaces, training, and "
            "support directly applicable to autonomous and remotely operated undersea vehicles."
        ),
        "activity_status": "active",
        "current_activity": (
            "Marine Sonic currently markets embedded side-scan sonar for autonomous underwater "
            "platforms and continues to provide products, training, and support from Yorktown."
        ),
        "activity_source_url": "https://www.marinesonic.com/",
        "activity_last_verified_at": "2026-08-24",
        "address_line": "120 Newsome Drive, Suite H",
        "city": "Yorktown",
        "state": "VA",
        "postal_code": "23692",
        "latitude": 37.185405,
        "longitude": -76.480533,
        "location_precision": "exact",
        "region": "Hampton Roads",
        "strategic_categories": [
            "Companies and solution providers",
            "Manufacturing and supply chain",
            "Core unmanned-systems asset",
        ],
        "platform_domains": ["Undersea systems"],
        "capabilities": [
            "Perception, sensing, and sensor fusion",
            "Payloads and mission systems",
            "Manufacturing, materials, and prototyping",
            "Systems engineering and integration",
        ],
        "missions": [
            "Maritime domain awareness",
            "Surveying and mapping",
            "Search and rescue",
        ],
        "website_url": "https://www.marinesonic.com/",
        "contact_text": "Marine Sonic Technology sales and support",
        "contact_phone": "757-463-0670",
        "contact_email": "Sales@US-TKMSgroup.com",
        "contact_url": "https://www.marinesonic.com/about-us",
        "sources": [
            {
                "title": "Marine Sonic AUV sonar products and Yorktown contact information",
                "url": "https://www.marinesonic.com/",
            },
            {
                "title": "Marine Sonic company background and operations",
                "url": "https://www.marinesonic.com/about-us",
            },
            {
                "title": "Marine Sonic AUV and ROV sonar product catalog",
                "url": "https://www.marinesonic.com/products",
            },
        ],
        "provenance": "curated-public-source",
    },
    {
        "name": "Linebird",
        "record_type": "organization",
        "short_description": (
            "Richmond company developing nonconductive UAS payloads and robotic tools for "
            "inspection, measurement, and maintenance of energized electric infrastructure."
        ),
        "overview": (
            "Linebird is a Richmond unmanned-systems company applying drones to electric-utility "
            "inspection and live-line work. Its Osprey Nonconductive Payload System carries "
            "sensors and tools so compatible UAS can contact energized transmission and "
            "distribution infrastructure."
        ),
        "unmanned_systems_relevance": (
            "Develops direct UAS payloads, end effectors, measurement tools, and integration "
            "methods for infrastructure inspection and physical work on power lines."
        ),
        "activity_status": "active",
        "current_activity": (
            "Linebird currently markets the Osprey platform and joined the Strategic Ventures "
            "portfolio in July 2026 to support continued utility-market growth."
        ),
        "activity_source_url": (
            "https://www.svrglobal.com/news-1/b64cf0a4-a15b-4be3-a2cb-64eaaf949bf3"
        ),
        "activity_last_verified_at": "2026-08-24",
        "address_line": "1717 East Cary Street",
        "city": "Richmond",
        "state": "VA",
        "postal_code": "23223",
        "latitude": 37.532252,
        "longitude": -77.428859,
        "location_precision": "exact",
        "region": "Greater Richmond",
        "strategic_categories": [
            "Companies and solution providers",
            "Manufacturing and supply chain",
            "Core unmanned-systems asset",
        ],
        "platform_domains": ["Unmanned aircraft systems"],
        "capabilities": [
            "Payloads and mission systems",
            "Manufacturing, materials, and prototyping",
            "Systems engineering and integration",
        ],
        "missions": ["Infrastructure inspection"],
        "website_url": "https://linebird.net/about/",
        "contact_text": "Linebird company and product inquiries",
        "contact_phone": "804-305-9763",
        "contact_email": "info@linebird.net",
        "contact_url": "https://linebird.net/about/",
        "sources": [
            {
                "title": "Linebird UAS payload technology and Richmond contact information",
                "url": "https://linebird.net/about/",
            },
            {
                "title": "Strategic Ventures Linebird portfolio update",
                "url": ("https://www.svrglobal.com/news-1/b64cf0a4-a15b-4be3-a2cb-64eaaf949bf3"),
            },
        ],
        "provenance": "curated-public-source",
    },
    {
        "name": "Ultra Maritime Chantilly Engineering Hub",
        "record_type": "facility",
        "short_description": (
            "Chantilly engineering hub for an undersea-warfare company with autonomous "
            "counter-UUV, unmanned sensing, USV radar, and rapid-fielding programs."
        ),
        "overview": (
            "Ultra Maritime identifies Chantilly as a U.S. engineering hub, distinct from its "
            "listed manufacturing sites. The company develops undersea-warfare systems, USV "
            "radar solutions, autonomous sensing, and counter-UUV technology, and in 2026 placed "
            "leadership for unmanned and rapid capability fielding in Chantilly."
        ),
        "unmanned_systems_relevance": (
            "Provides a documented Virginia engineering base tied directly to unmanned undersea "
            "capability development and rapid fielding; it is not represented as a manufacturing site."
        ),
        "activity_status": "active",
        "current_activity": (
            "Ultra Maritime currently lists Chantilly as an engineering hub and announced a "
            "Chantilly-based leader for unmanned anti-submarine-warfare and rapid-fielding solutions."
        ),
        "activity_source_url": "https://umaritime.com/ultra-maritime-david-adams/",
        "activity_last_verified_at": "2026-08-24",
        "address_line": "14585 Avion Parkway",
        "city": "Chantilly",
        "state": "VA",
        "postal_code": "20151",
        "latitude": 38.905716,
        "longitude": -77.449234,
        "location_precision": "exact",
        "region": "Northern Virginia",
        "strategic_categories": [
            "Companies and solution providers",
            "Research and technical depth",
            "Federal and defense customer access",
            "Core unmanned-systems asset",
        ],
        "platform_domains": ["Undersea systems", "Maritime surface systems"],
        "capabilities": [
            "Perception, sensing, and sensor fusion",
            "Payloads and mission systems",
            "Systems engineering and integration",
            "Testing, evaluation, verification, and validation",
        ],
        "missions": ["Maritime domain awareness", "ISR"],
        "website_url": "https://umaritime.com/",
        "contact_text": "Ultra Maritime Chantilly office",
        "contact_phone": "703-956-6480",
        "contact_email": "",
        "contact_url": "https://umaritime.com/contact-us/",
        "sources": [
            {
                "title": "Ultra Maritime unmanned capabilities and engineering hubs",
                "url": "https://umaritime.com/",
            },
            {
                "title": "Ultra Maritime Chantilly unmanned capability leadership",
                "url": "https://umaritime.com/ultra-maritime-david-adams/",
            },
            {
                "title": "Ultra Maritime Chantilly office address",
                "url": "https://umaritime.com/contact-us/",
            },
        ],
        "provenance": "curated-public-source",
    },
    {
        "name": "Hampton Roads Mobility Innovation Center",
        "record_type": "operating-environment",
        "short_description": (
            "Funded Newport News dual-site project for FAA-aligned UAS and AAM training, "
            "testing, research, BVLOS operations, and workforce development."
        ),
        "overview": (
            "The Hampton Roads Mobility Innovation Center is a funded, planned dual-site project "
            "anchored by Newport News-Williamsburg Airport and the Newport News Park Radio Control "
            "Club flying field. Public project materials describe an FAA-aligned environment for "
            "UAS and AAM testing, research, workforce training, BVLOS operations, and validation."
        ),
        "unmanned_systems_relevance": (
            "Would provide direct regional UAS test, training, research, workforce, and BVLOS "
            "infrastructure. It remains planned and does not yet imply operational availability "
            "or authorization for public flight testing."
        ),
        "activity_status": "planned",
        "current_activity": (
            "Newport News announced a $3.061 million GO Virginia award in May 2026 to develop the "
            "center. The public project description anticipates future operations and does not "
            "state that the BVLOS environment is currently open."
        ),
        "activity_source_url": "https://newportnewsva.com/mic/",
        "activity_last_verified_at": "2026-08-24",
        "address_line": "Newport News Park Radio Control Club Flying Field, Richneck Road",
        "city": "Newport News",
        "state": "VA",
        "postal_code": "23603",
        "latitude": 37.169681,
        "longitude": -76.509008,
        "location_precision": "site",
        "region": "Hampton Roads",
        "strategic_categories": [
            "Test and operational environments",
            "Workforce and talent",
            "Programs and initiatives",
            "Core unmanned-systems asset",
        ],
        "platform_domains": ["Unmanned aircraft systems", "Advanced Air Mobility"],
        "capabilities": [
            "Testing, evaluation, verification, and validation",
            "Safety, policy, regulatory, and airspace integration",
            "Operations, maintenance, and sustainment",
        ],
        "missions": ["Training and experimentation"],
        "website_url": "https://newportnewsva.com/mic/",
        "contact_text": "Newport News Economic Development Authority project inquiries",
        "contact_phone": "800-274-8348",
        "contact_email": "",
        "contact_url": "https://newportnewsva.com/contact/",
        "sources": [
            {
                "title": "Newport News Mobility Innovation Center award and dual-site plan",
                "url": "https://newportnewsva.com/mic/",
            },
            {
                "title": "GO Virginia Mobility Innovation Center implementation application",
                "url": (
                    "https://www.dhcd.virginia.gov/sites/default/files/DocX/gova/"
                    "board-docx/gova-board-packet-mar2026.pdf"
                ),
            },
            {
                "title": "Newport News Park Radio Control Club field and GPS location",
                "url": "https://newportnewsrc.org/",
            },
            {
                "title": "Newport News Economic Development Authority contact information",
                "url": "https://newportnewsva.com/contact/",
            },
        ],
        "provenance": "curated-public-source",
    },
]

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
        "Newport News/Williamsburg Intl",
        "supports",
        "Hampton Roads Mobility Innovation Center",
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
    detail = ASSET_DETAIL_ENRICHMENT.get(record["name"], {})
    for source_key in ASSET_DETAIL_SOURCE_KEYS.get(record["name"], ()):
        detail_source = source(source_key)
        if not any(item["url"] == detail_source["url"] for item in record["sources"]):
            record["sources"].append(detail_source)
    record.update(detail)

    for source_data in SOURCE_ENRICHMENT.get(record["name"], []):
        if not any(item["url"] == source_data["url"] for item in record["sources"]):
            record["sources"].append(source_data)

    website_override = WEBSITE_ENRICHMENT.get(record["name"])
    if website_override:
        record["website_url"] = website_override["url"]
        if not any(item["url"] == website_override["url"] for item in record["sources"]):
            record["sources"].append(
                {
                    "title": website_override["title"],
                    "url": website_override["url"],
                }
            )
        if website_override.get("activity_status"):
            record["activity_status"] = website_override["activity_status"]
            record["current_activity"] = website_override["current_activity"]
            record["activity_source_url"] = website_override["url"]
            record["activity_last_verified_at"] = CATALOG_DATE

    record.setdefault("overview", default_overview(record))
    record.setdefault("contact_phone", "")
    record.setdefault("contact_email", "")

    if not record.get("contact_url"):
        ranked_sources = sorted(record["sources"], key=contact_source_score, reverse=True)
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
            if contact_override.get(field) and field not in detail:
                record[field] = contact_override[field]
        if "contact_text" not in detail:
            record["contact_text"] = contact_scope(record)
        source_url = contact_override["source_url"]
        if not any(item["url"] == source_url for item in record["sources"]):
            record["sources"].append(
                {
                    "title": f"{record['name']} public contact information",
                    "url": source_url,
                }
            )

    priority_profile = PRIORITY_PROFILE_ENRICHMENT.get(record["name"])
    if priority_profile:
        for field in (
            "contact_text",
            "contact_phone",
            "contact_email",
            "contact_url",
            "activity_status",
            "current_activity",
            "partnership_opportunities",
            "activity_source_url",
        ):
            if field in priority_profile:
                record[field] = priority_profile[field]
        if priority_profile.get("current_activity"):
            record["activity_last_verified_at"] = priority_profile.get("reviewed_at", CATALOG_DATE)
        for source_data in priority_profile.get("sources", []):
            if not any(item["url"] == source_data["url"] for item in record["sources"]):
                record["sources"].append(source_data)

    if not any(item["url"] == record["contact_url"] for item in record["sources"]):
        record["sources"].append(
            {
                "title": f"{record['name']} public contact information",
                "url": record["contact_url"],
            }
        )
    return record


def apply_location_override(record):
    override = {
        **LOCATION_OVERRIDES.get(record["name"], {}),
        **LOCATION_ENRICHMENT.get(record["name"], {}),
    }
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
        if isinstance(location_source, dict):
            title, url = location_source["title"], location_source["url"]
        else:
            title, url = location_source
        if not any(item["url"] == url for item in record["sources"]):
            record["sources"].append({"title": title, "url": url})
    return record


def apply_university_campus_locations(records):
    """Use a documented parent campus for same-city university programs.

    The program source establishes the university association while IPEDS supplies
    the institution's public campus address. This is campus-level, not a claim that
    the marker identifies a particular laboratory room or operating site.
    """
    records_by_name = {record["name"]: record for record in records}
    for parent_name, _relationship_type, child_name in university_relationships():
        parent = records_by_name.get(parent_name)
        child = records_by_name.get(child_name)
        if not parent or not child:
            continue
        if child.get("address_line") or child.get("location_precision") not in {
            "approximate",
            "locality",
        }:
            continue
        if child.get("city", "").casefold() != parent.get("city", "").casefold():
            continue
        if not parent.get("address_line"):
            continue

        for field in (
            "address_line",
            "city",
            "postal_code",
            "latitude",
            "longitude",
            "region",
        ):
            child[field] = parent.get(field, "")
        child["location_precision"] = "site"
        if not any(item["url"] == IPEDS_DIRECTORY_PAGE for item in child["sources"]):
            child["sources"].append(
                {
                    "title": f"{parent_name} campus location (NCES IPEDS 2024)",
                    "url": IPEDS_DIRECTORY_PAGE,
                }
            )
    return records


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
        [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
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


def faa_airport_record_url(identifier):
    params = urllib.parse.urlencode(
        {
            "where": f"IDENT='{identifier}'",
            "outFields": "IDENT,NAME,OPERSTATUS",
            "returnGeometry": "false",
            "f": "html",
        }
    )
    return f"{FAA_LAYER}/query?{params}"


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
        faa_record_source = {
            "title": f"FAA airport record for {name} ({identifier})",
            "url": faa_airport_record_url(identifier),
        }
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
                "strategic_categories": ecosystem_role_categories(
                    ["Physical infrastructure and logistics"], core=False
                ),
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
                "sources": [faa_record_source, faa_source, doav_source, sponsor_source],
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
                    "strategic_categories": ecosystem_role_categories(
                        ["Federal and defense customer access"], core=False
                    ),
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
        if not (row["STABBR"] == "VA" and row["CYACTIVE"] == "1" and row["DEGGRANT"] == "1"):
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
        return f"Private nonprofit degree-granting college or university based in {city}, Virginia."
    return f"Private degree-granting university based in {city}, Virginia."


def university_records():
    detailed_assets = {item[0]: item for item in UNIVERSITY_ASSETS}
    records = []
    for row in eligible_virginia_institutions():
        name = row["catalog_name"]
        if name in SPECIALIZED_HIGHER_ED_EXCLUSIONS:
            continue
        detailed_asset = detailed_assets.get(name)
        latitude = round(float(row["LATITUDE"]), 6)
        longitude = round(float(row["LONGITUD"]), 6)
        website_url = normalize_public_url(row["WEBADDR"])
        contact_url = (
            normalize_public_url(row["ADMINURL"])
            if row.get("ADMINURL", "").strip()
            else website_url
        )
        contact_url = INSTITUTION_CONTACT_OVERRIDES.get(name, contact_url)
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
        if not any(item["url"] == website_url for item in record_sources):
            record_sources.append(
                {
                    "title": f"{name} official website",
                    "url": website_url,
                }
            )
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
                    "strategic_categories": ecosystem_role_categories(categories, core=False),
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
                    "strategic_categories": ecosystem_role_categories(
                        profile["categories"],
                        core=profile_key not in SUPPORTING_PROFILE_KEYS,
                    ),
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
        if not record.get("website_url") or not any(
            item["url"] == record["website_url"] for item in record["sources"]
        ):
            raise ValueError(f"Primary website is not source-backed: {record['name']}")
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
            if not record.get("activity_source_url") or not record.get("activity_last_verified_at"):
                raise ValueError(f"Unverified activity details: {record['name']}")
            if not any(item["url"] == record["activity_source_url"] for item in record["sources"]):
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
                item["url"] == record["development_source_url"] for item in record["sources"]
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
        role_categories = {
            CORE_ASSET_CATEGORY,
            SUPPORTING_ASSET_CATEGORY,
        }.intersection(record["strategic_categories"])
        if len(role_categories) != 1:
            raise ValueError(f"Invalid ecosystem role classification: {record['name']}")

    relationship_assets = {
        asset_name
        for relationship in relationships
        for asset_name in (relationship[0], relationship[2])
    }
    unknown_assets = relationship_assets - names
    if unknown_assets:
        raise ValueError(f"Unknown relationship assets: {', '.join(sorted(unknown_assets))}")

    unknown_source_enrichment = set(SOURCE_ENRICHMENT) - names
    if unknown_source_enrichment:
        raise ValueError(
            f"Unknown source-enrichment assets: {', '.join(sorted(unknown_source_enrichment))}"
        )


def main():
    records = (
        airport_records()
        + defense_records()
        + university_records()
        + curated_records()
        + VERIFIED_UXS_ADDITIONS
        + VERIFIED_UXS_EXPANSION
    )
    records = [finalize_record(apply_location_override(record)) for record in records]
    records = apply_university_campus_locations(records)
    records.sort(key=lambda item: item["name"].casefold())
    relationships = list(CATALOG_RELATIONSHIPS) + university_relationships()
    relationships.extend(
        ("Virginia Department of Aviation", "supports", record["name"])
        for record in records
        if record["provenance"] == "faa-public-airport"
    )
    validate(records, relationships)
    payload = {
        "generated_at": BUILD_DATE,
        "record_count": len(records),
        "methodology": (
            "Current operational public-use aviation facilities from the FAA feature service, "
            "publicly listed installations from the Virginia Military Factbook, broad-based "
            "Virginia degree-granting institutions from the NCES IPEDS 2024 directory while "
            "excluding narrowly specialized health and ministry schools without documented "
            "unmanned-systems relevance, and a curated set of source-backed ecosystem "
            "records. Specific street and site locations are "
            "anchored to official public address sources and geocoded against the U.S. Census "
            "address ranges or named-site map data; locality points are retained when the public "
            "record does not identify the operating department or facility. Every record is also "
            "classified as either a core unmanned-systems asset with direct documented activity "
            "or a supporting ecosystem asset with a broader enabling role."
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
