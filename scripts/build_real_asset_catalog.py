#!/usr/bin/env python3
"""Build the checked-in Virginia real-asset catalog from public sources."""

import json
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "virginia_real_assets.json"
CATALOG_DATE = "2026-07-20"

FAA_LAYER = (
    "https://services6.arcgis.com/ssFJjBXIUyZDrSYZ/ArcGIS/rest/services/US_Airport/FeatureServer/0"
)
DOAV_DIRECTORY = "https://doav.virginia.gov/airport-directory/"
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

SOURCES = {
    "vedp": ("VEDP: Unmanned Systems in Virginia", VEDP_UXS),
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
    "xelevate": ("Xelevate Leesburg Unmanned Systems Facility", "https://xelevateus.com/leesburg-virginia/"),
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
        "Accomack County Emergency Management Drone Program",
        "https://www.co.accomack.va.us/home/showpublisheddocument/19584/638920698825370000",
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
        "domains": ["Unmanned aircraft systems", "Ground vehicles and robotics", "Cross-domain autonomy"],
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
        "domains": ["Unmanned aircraft systems", "Ground vehicles and robotics", "Maritime surface systems"],
        "capabilities": ["Testing, evaluation, verification, and validation", "Systems engineering and integration"],
        "missions": ["Training and experimentation"],
        "relevance": (
            "Provides a publicly documented environment for unmanned-system testing, training, "
            "demonstration, validation, or operational integration."
        ),
    },
    "public_safety": {
        "categories": ["Programs and initiatives", "Multi-domain missions"],
        "domains": ["Unmanned aircraft systems"],
        "capabilities": ["Operations, maintenance, and sustainment", "Perception, sensing, and sensor fusion"],
        "missions": ["Public safety and emergency response", "Search and rescue", "Surveying and mapping"],
        "relevance": (
            "Operates, coordinates, or funds a documented public-sector UAS capability for "
            "emergency response, mapping, inspection, conservation, or public safety."
        ),
    },
    "agriculture": {
        "categories": ["Research and technical depth", "Programs and initiatives"],
        "domains": ["Unmanned aircraft systems"],
        "capabilities": ["Perception, sensing, and sensor fusion", "Data engineering, analytics, and edge computing"],
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
}

PLACES = {
    "Accomac": (37.720, -75.665),
    "Abingdon": (36.710, -81.975),
    "Afton": (38.029, -78.835),
    "Arlington": (38.881, -77.091),
    "Blackstone": (37.080, -77.997),
    "Blacksburg": (37.229, -80.414),
    "Bowling Green": (38.050, -77.347),
    "Charlottesville": (38.035, -78.503),
    "Chesapeake": (36.768, -76.288),
    "Chester": (37.356, -77.442),
    "Christiansburg": (37.130, -80.409),
    "Clifton Forge": (37.817, -79.824),
    "Danville": (36.586, -79.395),
    "Dahlgren": (38.333, -77.031),
    "Dulles": (38.955, -77.448),
    "Eastville": (37.352, -75.946),
    "Farmville": (37.302, -78.391),
    "Fairfax": (38.846, -77.307),
    "Fredericksburg": (38.303, -77.461),
    "Front Royal": (38.918, -78.194),
    "Glen Allen": (37.666, -77.506),
    "Hampton": (37.030, -76.346),
    "Harrisonburg": (38.449, -78.869),
    "Henrico": (37.632, -77.515),
    "Lynchburg": (37.414, -79.142),
    "Leesburg": (39.116, -77.564),
    "Lorton": (38.704, -77.228),
    "Manassas": (38.751, -77.475),
    "Melfa": (37.649, -75.741),
    "Middletown": (39.027, -78.280),
    "Newport News": (37.087, -76.473),
    "Norfolk": (36.851, -76.286),
    "Portsmouth": (36.836, -76.298),
    "Petersburg": (37.227, -77.402),
    "Prince George": (37.221, -77.289),
    "Quantico": (38.522, -77.290),
    "Radford": (37.132, -80.576),
    "Reston": (38.959, -77.357),
    "Richmond": (37.541, -77.436),
    "Roanoke": (37.271, -79.941),
    "Rustburg": (37.276, -79.100),
    "Springfield": (38.789, -77.187),
    "Sterling": (39.006, -77.428),
    "Sedley": (36.790, -76.590),
    "Suffolk": (36.728, -76.584),
    "Virginia Beach": (36.853, -75.978),
    "Wallops Island": (37.940, -75.467),
    "Williamsburg": (37.271, -76.707),
    "Weyers Cave": (38.288, -78.913),
    "Wise": (36.975, -82.576),
    "Winchester": (39.185, -78.163),
    "Yorktown": (37.239, -76.510),
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
    ("Naval Support Activity Northwest Annex", "Virginia Beach", "Hampton Roads"),
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
        "state",
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
        "state",
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
        "state",
        "Commonwealth aviation program covering automated small uncrewed systems, remotely controlled aircraft, and aviation automation.",
        "doav_aam",
    ),
    (
        "Virginia Flight Information Exchange",
        "program",
        "Blacksburg",
        "New River Valley",
        "state",
        "Statewide information-sharing capability supporting safe and informed UAS operations.",
        "vipc",
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
]


def source(key):
    title, url = SOURCES[key]
    return {"title": title, "url": url}


def region_for(latitude, longitude):
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
    faa_source = {
        "title": "FAA Airports Feature Service",
        "url": FAA_LAYER,
    }
    doav_source = {
        "title": "Virginia Public-use Airport Directory",
        "url": DOAV_DIRECTORY,
    }
    for feature in fetch_public_airports():
        properties = feature["properties"]
        longitude, latitude = feature["geometry"]["coordinates"][:2]
        name = properties["NAME"].strip()
        city = properties["SERVCITY"].replace("/", " / ").title()
        identifier = properties["IDENT"]
        records.append(
            {
                "name": name,
                "record_type": "infrastructure",
                "short_description": (
                    f"Operational public-use Virginia aviation facility (FAA identifier {identifier})."
                ),
                "unmanned_systems_relevance": (
                    f"{name} is included as public aviation infrastructure serving {city}. "
                    "Its inclusion does not imply authorization for unmanned-aircraft operations; "
                    "airport, operator, and airspace approvals still apply."
                ),
                "city": city,
                "state": "VA",
                "latitude": round(latitude, 6),
                "longitude": round(longitude, 6),
                "location_precision": "exact",
                "region": region_for(latitude, longitude),
                "strategic_categories": ["Physical infrastructure and logistics"],
                "platform_domains": ["Unmanned aircraft systems"],
                "capabilities": ["Operations, maintenance, and sustainment"],
                "missions": [],
                "website_url": DOAV_DIRECTORY,
                "sources": [faa_source, doav_source],
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
    return records


def university_records():
    records = []
    for name, place, region, description, source_key, _children in UNIVERSITY_ASSETS:
        latitude, longitude = PLACES[place]
        record_source = source(source_key)
        records.append(
            {
                "name": name,
                "record_type": "university",
                "short_description": description,
                "unmanned_systems_relevance": (
                    f"{name} is mapped at the institution level to connect its source-backed "
                    "unmanned-systems research, education, operations, facilities, and programs."
                ),
                "city": place,
                "state": "VA",
                "latitude": latitude,
                "longitude": longitude,
                "location_precision": "locality",
                "region": region,
                "strategic_categories": ["Research and technical depth", "Workforce and talent"],
                "platform_domains": ["Cross-domain autonomy"],
                "capabilities": [
                    "Autonomy and artificial intelligence",
                    "Systems engineering and integration",
                ],
                "missions": ["Training and experimentation"],
                "website_url": record_source["url"],
                "sources": [record_source],
                "provenance": "university-institution",
            }
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
        record_source = source(source_key)
        records.append(
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
                "website_url": record_source["url"],
                "sources": [record_source],
                "provenance": "curated-public-source",
            }
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
        if not (-90 <= record["latitude"] <= 90 and -180 <= record["longitude"] <= 180):
            raise ValueError(f"Invalid coordinates: {record['name']}")
        if len(record["short_description"]) > 320:
            raise ValueError(f"Description too long: {record['name']}")

    relationship_assets = {
        asset_name for relationship in relationships for asset_name in (relationship[0], relationship[2])
    }
    unknown_assets = relationship_assets - names
    if unknown_assets:
        raise ValueError(f"Unknown relationship assets: {', '.join(sorted(unknown_assets))}")


def main():
    records = airport_records() + defense_records() + university_records() + curated_records()
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
            "publicly listed installations from the Virginia Military Factbook, and a curated "
            "set of source-backed ecosystem records."
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
