"""
Sample corpora for modulation simulation testing.

All text is original, written in the style of institutional communications.
No real quotes from real documents. For simulation and research use only.
"""

# ---------------------------------------------------------------------------
# Institutional text samples (Federal Reserve / Congressional / Central Bank)
# ---------------------------------------------------------------------------

SAMPLE_INSTITUTIONAL_TEXT: list[str] = [
    # Federal Reserve style
    (
        "The Committee seeks to achieve maximum employment and price stability "
        "consistent with its statutory mandate. Participants noted that the "
        "labor market remains robust, with job gains continuing at a solid pace "
        "across most sectors. Inflation has moderated but remains above the "
        "Committee's longer-run objective of two percent. The Committee judges "
        "that the risks to achieving its dual mandate are broadly balanced."
    ),
    # Congressional style
    (
        "Be it enacted by the Senate and House of Representatives of the United "
        "States of America in Congress assembled, that the following provisions "
        "shall take effect upon enactment. Section one of this Act shall be cited "
        "as the Distributed Infrastructure and Bandwidth Efficiency Research Act. "
        "Nothing in this Act shall be construed to authorize the use of any "
        "portion of the electromagnetic spectrum for unlicensed transmission."
    ),
    # Central bank style
    (
        "The Governing Council will continue to follow a data-dependent approach "
        "to determining the appropriate level and duration of restriction. Future "
        "decisions will remain calibrated to incoming economic data, the evolving "
        "inflation outlook, and the strength of monetary policy transmission. "
        "The Council stands ready to adjust all of its instruments within its "
        "mandate to ensure that inflation returns sustainably to its target."
    ),
    # Federal Reserve style — meeting minutes
    (
        "In their discussion of the economic outlook, participants generally "
        "assessed that economic activity had continued to expand at a moderate "
        "pace. Consumer spending growth had remained resilient despite elevated "
        "financing costs. Housing sector activity had shown signs of stabilization "
        "following a period of contraction. Business fixed investment had been "
        "subdued, reflecting cautious corporate sentiment amid ongoing policy "
        "uncertainty. The unemployment rate had remained low and little changed."
    ),
    # Congressional testimony style
    (
        "Chairman, Ranking Member, and distinguished members of the Committee, "
        "thank you for the opportunity to appear before you today to discuss "
        "the state of the communications infrastructure and the policy challenges "
        "associated with spectrum allocation and bandwidth efficiency. The agency "
        "has undertaken a comprehensive review of its licensing framework and "
        "anticipates publishing proposed rulemaking for public comment within "
        "the next fiscal quarter. We welcome congressional oversight on these matters."
    ),
    # Central bank policy statement
    (
        "The Monetary Policy Committee voted at its most recent meeting to maintain "
        "the policy rate at its current level, consistent with returning inflation "
        "sustainably to the target over the medium term. The Committee noted that "
        "services price inflation remains elevated and that underlying inflation "
        "pressures are moderating only gradually. The Committee will review its "
        "stance at each subsequent meeting in light of developments in the economy, "
        "financial conditions, and the inflation trajectory."
    ),
    # Regulatory agency style
    (
        "The Commission finds, based on the record in this proceeding, that the "
        "public interest, convenience, and necessity will be served by the grant "
        "of the applications as filed. The Commission has determined that the "
        "proposed operations are consistent with the Commission's rules and policies "
        "and that no significant environmental impact is anticipated. The applicant "
        "is advised that this authorization does not constitute an endorsement of "
        "the technical specifications or operational parameters described herein."
    ),
    # Treasury-style fiscal communication
    (
        "The Department of the Treasury projects that the federal government will "
        "exhaust its borrowing capacity under the statutory limit within the window "
        "specified in prior correspondence. The Secretary urges the Congress to act "
        "promptly to address the debt limit, as failure to do so would impose severe "
        "and lasting harm on the creditworthiness of the United States and on the "
        "global financial system. Treasury continues to employ available extraordinary "
        "measures consistent with its fiduciary responsibilities."
    ),
]

# ---------------------------------------------------------------------------
# Sensor data samples (JSON strings similar to SpatialRecord sensor_data)
# ---------------------------------------------------------------------------

SAMPLE_SENSOR_DATA: list[str] = [
    '{"temp_c": 32.1, "humidity": 0.78, "signal_rssi": -67, '
    '"node_id": "4a2f", "seq": 1, "batt_mv": 3712}',

    '{"temp_c": 18.4, "humidity": 0.55, "signal_rssi": -82, '
    '"node_id": "9b1c", "seq": 14, "batt_mv": 3480, '
    '"pressure_hpa": 1013.2, "co2_ppm": 412}',

    '{"temp_c": 25.0, "humidity": 0.61, "signal_rssi": -54, '
    '"node_id": "2d7e", "seq": 7, "batt_mv": 3901, '
    '"accel_x": 0.02, "accel_y": -0.01, "accel_z": 9.81}',

    '{"event": "motion_detected", "zone": "perimeter_north", '
    '"confidence": 0.93, "node_id": "7f3a", "seq": 203, '
    '"signal_rssi": -71, "batt_mv": 3650}',

    '{"temp_c": 41.7, "humidity": 0.21, "signal_rssi": -90, '
    '"node_id": "c5e9", "seq": 88, "batt_mv": 3210, '
    '"solar_mv": 4200, "charge_state": "charging", '
    '"gateway_id": "gw-001", "hops": 3}',
]

# ---------------------------------------------------------------------------
# Mesh-style messages
# ---------------------------------------------------------------------------

SAMPLE_MESH_MESSAGES: list[str] = [
    "Node 4a2f reporting: spatial sync complete, 3 peers visible, "
    "channel quality 87%, last hop latency 12ms",

    "Node 9b1c alert: link to node 7f3a degraded, RSSI dropped to -91dBm, "
    "switching to fallback route via node 2d7e",

    "Node 2d7e heartbeat: uptime 14d 6h 22m, queue depth 0, "
    "firmware v2.3.1, battery 91%, solar nominal",

    "Gateway gw-001 status: 12 nodes registered, 2 nodes unreachable, "
    "uplink latency 340ms, packet loss 0.3%, compression active",

    "Node c5e9 discovery: new peer detected at range ~180m, "
    "signal strength -68dBm, negotiating session keys, mesh joining",
]
