"""
Section-building helpers for the Ultimate Guide PDF.

These functions are extracted from the original build_ultimate_guide module so
rendering logic lives in the renderer layer. They rely on a `core` module
instance (the original build_ultimate_guide) for data and utilities.
"""

from reportlab.platypus import (
    Paragraph,
    Spacer,
    Image,
    Table,
    TableStyle,
    PageBreak,
    Flowable,
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from xml.sax.saxutils import escape


class USMapFlowable(Flowable):
    """
    Custom Flowable that draws a background map of the US and places a marker
    for each school based on lat/lon.
    """

    def __init__(self, core, width, height, image_path, schools):
        super().__init__()
        self.core = core
        self.width = width
        self.height = height
        self.image_path = image_path
        self.schools = schools

    def draw(self):
        c = self.canv

        # Draw the base US map image
        try:
            c.drawImage(
                str(self.image_path),
                0,
                0,
                width=self.width,
                height=self.height,
                preserveAspectRatio=True,
                mask="auto",
            )
        except Exception:
            # If the image is missing, just draw a simple rectangle placeholder
            c.setStrokeColor(colors.grey)
            c.rect(0, 0, self.width, self.height)

        # Plot each school as a small logo marker (fallback to circle)
        for s in self.schools:
            # If manual normalized coordinates are provided, use them.
            map_x = s.get("map_x")
            map_y = s.get("map_y")

            if map_x is not None and map_y is not None:
                norm_x = max(0.0, min(1.0, float(map_x)))
                norm_y = max(0.0, min(1.0, float(map_y)))
            else:
                lat = s.get("lat")
                lon = s.get("lon")
                if lat is None or lon is None:
                    continue
                norm_x = (lon - self.core.US_MIN_LON) / (self.core.US_MAX_LON - self.core.US_MIN_LON)
                norm_y = (lat - self.core.US_MIN_LAT) / (self.core.US_MAX_LAT - self.core.US_MIN_LAT)
                norm_x = max(0.0, min(1.0, norm_x))
                norm_y = max(0.0, min(1.0, norm_y))

            x = norm_x * self.width
            y = norm_y * self.height

            fname = self.core.LOGO_MAP.get(s["name"], self.core.LOGO_MAP.get(s["name"].replace(" (UConn)", ""), None))
            logo_path = self.core.PNG_DIR / fname if fname else None

            if logo_path and logo_path.exists():
                logo_w = 0.32 * inch
                logo_h = 0.25 * inch
                c.drawImage(
                    str(logo_path),
                    x - logo_w / 2,
                    y - logo_h / 2,
                    width=logo_w,
                    height=logo_h,
                    mask="auto",
                    preserveAspectRatio=True,
                )
            else:
                c.setFillColor(colors.red)
                c.setStrokeColor(colors.white)
                radius = 4
                c.circle(x, y, radius, fill=1, stroke=1)


def build_map_page(core, story, styles):
    """Add a page that shows a US map with a marker for each school."""
    heading = ParagraphStyle(
        "h_map",
        parent=styles["Heading2"],
        fontSize=14,
        leading=18,
        alignment=1,
    )

    story.append(Spacer(1, 0.4 * inch))
    story.append(Paragraph("Target Schools – Geographic Overview", heading))
    story.append(Spacer(1, 0.3 * inch))

    map_width = 7.2 * inch
    map_height = map_width * (665 / 1024)  # preserve source image aspect

    if core.US_MAP_IMAGE.exists():
        map_flowable = USMapFlowable(
            core=core,
            width=map_width,
            height=map_height,
            image_path=core.US_MAP_IMAGE,
            schools=core.SCHOOLS,
        )
        story.append(map_flowable)
    else:
        story.append(Paragraph("Map image not found; skipping map page.", styles["BodyText"]))

    story.append(PageBreak())


def build_cover_page(core, story, styles):
    """Add cover page to story."""
    title_style = ParagraphStyle(
        'title',
        parent=styles['Title'],
        alignment=1,
        fontSize=24,
        leading=30,
    )
    subtitle_style = ParagraphStyle(
        'subtitle',
        parent=styles['BodyText'],
        alignment=1,
        fontSize=12,
        leading=16,
    )
    personal_style = ParagraphStyle(
        'personal',
        parent=styles['BodyText'],
        alignment=1,
        fontSize=11,
        leading=14,
    )

    story.append(Spacer(1, 0.6 * inch))
    story.append(Paragraph("2025 Transfer Opportunity Analysis – Setter Edition", title_style))
    story.append(Spacer(1, 0.15 * inch))
    story.append(Paragraph(
        "A comprehensive analysis of setter depth, opportunity, culture & travel logistics",
        subtitle_style,
    ))
    story.append(Spacer(1, 0.35 * inch))

    cols = 5
    logo_width = 1.1 * inch
    logo_height = 0.9 * inch
    cells = []
    row = []

    for idx, s in enumerate(core.SCHOOLS):
        fname = core.LOGO_MAP.get(s["name"], core.LOGO_MAP.get(s["name"].replace(" (UConn)", ""), None))
        if fname:
            path = core.PNG_DIR / fname
            if path.exists():
                cell = Image(str(path), width=logo_width, height=logo_height)
            else:
                cell = Paragraph(s["short"], styles['BodyText'])
        else:
            cell = Paragraph(s["short"], styles['BodyText'])
        row.append(cell)
        if (idx + 1) % cols == 0:
            cells.append(row)
            row = []

    if row:
        while len(row) < cols:
            row.append("")
        cells.append(row)

    table = Table(
        cells,
        colWidths=[(7.5 * inch) / cols] * cols
    )
    table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))

    story.append(table)
    story.append(Spacer(1, 0.4 * inch))
    player_name = getattr(core, "PLAYER", None) and getattr(core.PLAYER, "name", "Player") or "Player"
    player_height = getattr(core, "PLAYER", None) and getattr(core.PLAYER, "height", None)
    player_hand = getattr(core, "PLAYER", None) and getattr(core.PLAYER, "handedness", None)
    player_pos = getattr(core, "PLAYER", None) and getattr(core.PLAYER, "position", None)
    player_home_city = getattr(core, "PLAYER", None) and getattr(core.PLAYER, "home_city", None)
    player_home_state = getattr(core, "PLAYER", None) and getattr(core.PLAYER, "home_state", None)

    personal_bits = [f"<b>{player_name}</b>"]
    if player_height or player_hand or player_pos:
        detail = " – ".join(
            [
                part for part in [
                    player_height,
                    f"{player_hand}-Handed" if player_hand else None,
                    player_pos,
                ] if part
            ]
        )
        if detail:
            personal_bits.append(detail)
    if player_home_city or player_home_state:
        home = ", ".join([p for p in [player_home_city, player_home_state] if p])
        personal_bits.append(f"Home: {home}")

    story.append(Paragraph(" – ".join(personal_bits), personal_style))
    story.append(PageBreak())


def build_fit_score_table(core, story, styles):
    """Add a table ranking schools by Fit Score (with RPI)."""
    heading = ParagraphStyle(
        'h_fit',
        parent=styles['Heading2'],
        fontSize=14,
        leading=18,
    )
    story.append(Paragraph("Overall Fit Score Ranking", heading))
    story.append(Spacer(1, 0.15 * inch))

    sorted_schools = sorted(core.SCHOOLS, key=lambda x: x["fit_score"], reverse=True)
    data = [["Rank", "School", "Tier", "RPI", "Fit Score", "VB Opp", "Geo Score"]]
    for i, s in enumerate(sorted_schools, start=1):
        rpi_display = (
            f"{int(s['rpi_rank'])}"
            if isinstance(s.get("rpi_rank"), (int, float))
            else "N/A"
        )
        data.append([
            i,
            s["short"],
            s["tier"],
            rpi_display,
            f"{s['fit_score']:.2f}",
            f"{s['vb_opp_score']:.1f}",
            f"{s['geo_score']:.1f}",
        ])

    table = Table(
        data,
        colWidths=[0.5*inch, 2.1*inch, 0.6*inch, 0.7*inch, 0.9*inch, 0.9*inch, 0.9*inch],
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("ALIGN", (1, 1), (1, -1), "LEFT"),
    ]))

    story.append(table)
    story.append(PageBreak())


def build_travel_matrix(core, story, styles):
    """Add a travel distance matrix."""
    heading = ParagraphStyle(
        'h_travel',
        parent=styles['Heading2'],
        fontSize=14,
        leading=18,
    )
    story.append(Paragraph("Travel Snapshot (from home)", heading))
    story.append(Spacer(1, 0.15 * inch))

    data = [["School", "Drive (mi)", "Drive (hr)", "Flight (mi)", "Flight (hr)", "Travel Diff"]]
    for s in core.SCHOOLS:
        data.append([
            s["short"],
            f"{s['drive_dist_mi']:.0f}",
            f"{s['drive_time_hr']:.1f}",
            f"{s['flight_dist_mi']:.0f}",
            f"{s['flight_time_hr']:.2f}",
            str(s["travel_difficulty"]),
        ])

    table = Table(data, colWidths=[2.2*inch, 0.9*inch, 0.9*inch, 0.9*inch, 0.9*inch, 1.0*inch])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
        ("ALIGN", (0, 1), (0, -1), "LEFT"),
    ]))

    story.append(table)
    story.append(PageBreak())


def build_school_pages(core, story, styles):
    """Add a dedicated page for each school with detail + roster snapshot."""
    heading = ParagraphStyle(
        'h_school',
        parent=styles['Heading2'],
        fontSize=16,
        leading=20,
    )
    sub = ParagraphStyle(
        'sub_school',
        parent=styles['BodyText'],
        fontSize=10,
        leading=13,
    )
    roster_heading = ParagraphStyle(
        'h_roster',
        parent=styles['Heading3'],
        fontSize=11,
        leading=13,
        alignment=1,
    )
    notes_heading = ParagraphStyle(
        'h_notes',
        parent=styles['Heading2'],
        fontSize=13,
        leading=16,
        alignment=1,
    )

    def add_notes_page(school_name: str):
        story.append(PageBreak())
        story.append(Paragraph(f"{school_name} – Notes", notes_heading))
        story.append(Spacer(1, 0.15 * inch))
        line_count = 32
        lines = [[""] for _ in range(line_count)]
        notes_table = Table(lines, colWidths=[6.5 * inch])
        notes_table.setStyle(TableStyle([
            ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#7da7d9")),
            ("LINEBEFORE", (0, 0), (0, -1), 0.75, colors.HexColor("#d77a7a")),
            ("BOX", (0, 0), (-1, -1), 1.0, colors.HexColor("#7da7d9")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWHEIGHT", (0, 0), (-1, -1), 0.30 * inch),
        ]))
        story.append(notes_table)
        story.append(PageBreak())

    for s in core.SCHOOLS:
        story.append(Paragraph(s["name"], heading))
        story.append(Spacer(1, 0.08 * inch))

        fname = core.LOGO_MAP.get(s["name"], core.LOGO_MAP.get(s["name"].replace(" (UConn)", ""), None))
        if fname:
            path = core.PNG_DIR / fname
            if path.exists():
                img = Image(str(path), width=1.5 * inch, height=1.1 * inch)
                niche = core.NICHE_DATA.get(s["name"], {})
                overall_grade = niche.get("overall_grade", "N/A")
                academics_grade = niche.get("academics_grade", "N/A")
                value_grade = niche.get("value_grade", "N/A")
                rpi_display = (
                    f"{int(s['rpi_rank'])}"
                    if isinstance(s.get("rpi_rank"), (int, float))
                    else "N/A"
                )
                record_display = s.get("record", "N/A")
                politics_label = s.get("politics_label") or "N/A"

                left_para = Paragraph(
                    f"<b>Location:</b> {s['city_state']}<br/>"
                    f"<b>Conference:</b> {s['conference']}<br/>"
                    f"<b>Academic Tier:</b> {s['tier']}<br/>"
                    f"<b>Offense Type:</b> {s['offense_type']}<br/>"
                    f"<b>RPI Rank:</b> {rpi_display}<br/>"
                    f"<b>Record:</b> {record_display}<br/>"
                    f"<b>Fit Score:</b> {s['fit_score']} / 3.0<br/>"
                    f"<b>Campus politics:</b> {politics_label}",
                    sub
                )

                right_para = Paragraph(
                    f"<b>Niche Snapshot:</b><br/>"
                    f"Overall: {overall_grade} &nbsp; "
                    f"Academics: {academics_grade} &nbsp; "
                    f"Value: {value_grade}",
                    sub
                )

                info_table = Table([[img, left_para], ["", right_para]])
                info_table.setStyle(TableStyle([
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]))
                story.append(info_table)
            else:
                story.append(Paragraph(f"[Logo missing: {fname}]", styles['BodyText']))
        else:
            story.append(Paragraph("[Logo not mapped]", styles['BodyText']))

        story.append(Spacer(1, 0.1 * inch))

        travel_text = (
            f"<b>Travel from home:</b><br/>"
            f"Approx. driving distance: {s['drive_dist_mi']} miles "
            f"(~{s['drive_time_hr']} hrs)<br/>"
            f"Great-circle flight distance: {s['flight_dist_mi']} miles "
            f"(~{s['flight_time_hr']} hrs in-air)<br/>"
            f"Travel Difficulty Score: {s['travel_difficulty']} / 100"
        )
        story.append(Paragraph(travel_text, sub))
        story.append(Spacer(1, 0.1 * inch))

        info = core.AIRPORT_INFO.get(s["name"])
        if info and s.get("drive_dist_mi", 0) > 350:
            airport_name = info["airport_name"]
            airport_code = info["airport_code"]
            drive_time = info.get("airport_drive_time", "N/A")
            notes = info["notes_from_indy"]

            air_rows = [
                [Paragraph("<b>Air Travel Notes</b>", sub)],
                [Paragraph(f"Nearest major airport: {airport_name} ({airport_code})", sub)],
                [Paragraph(f"Approx. drive to airport: {drive_time}", sub)],
                [Paragraph(f"From IND: {notes}", sub)],
            ]

            air_table = Table(
                air_rows,
                colWidths=[6.5 * inch],
            )
            air_table.setStyle(TableStyle([
                ("BOX", (0, 0), (-1, -1), 0.75, colors.grey),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                ("BACKGROUND", (0, 0), (0, 0), colors.whitesmoke),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))

            story.append(air_table)
            story.append(Spacer(1, 0.12 * inch))

        risk_text = s.get("risk_watchouts") or core.RISK_WATCHOUTS.get(s["name"])
        if risk_text:
            story.append(
                Paragraph(f"<b>Risk / Watchouts:</b> {risk_text}", sub)
            )
            story.append(Spacer(1, 0.1 * inch))

        coaches = s.get("coaches", [])
        if coaches:
            story.append(Paragraph("<b>Staff Contacts (top 3)</b>", sub))
            coach_rows = [["Name", "Title", "Contact"]]
            for c in coaches[:3]:
                contact_lines = []
                email = c.get("email", "")
                phone = core.normalize_phone(c.get("phone", ""))
                if email:
                    contact_lines.append(escape(email))
                if phone:
                    contact_lines.append(escape(phone))
                contact_html = "<br/>".join(contact_lines) if contact_lines else ""
                contact = Paragraph(contact_html, sub) if contact_html else Paragraph("", sub)
                coach_rows.append([
                    c.get("name", ""),
                    c.get("title", ""),
                    contact,
                ])
            coach_table = Table(
                coach_rows,
                colWidths=[1.9*inch, 1.7*inch, 2.6*inch],
            )
            coach_table.setStyle(TableStyle([
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("BOX", (0, 0), (-1, -1), 0.25, colors.grey),
            ]))
            story.append(coach_table)
            story.append(Spacer(1, 0.1 * inch))

        niche = core.NICHE_DATA.get(s["name"], {})
        summary = niche.get("summary", "")
        review_pos = niche.get("review_pos", "")
        review_neg = niche.get("review_neg", "")

        if summary:
            story.append(Paragraph(f"<b>Campus & Academic Vibe:</b> {summary}", sub))
            story.append(Spacer(1, 0.08 * inch))

        if review_pos:
            story.append(Paragraph(f"<b>Student Review (Positive):</b> {review_pos}", sub))
            story.append(Spacer(1, 0.05 * inch))
        if review_neg:
            story.append(Paragraph(f"<b>Student Review (Critical):</b> {review_neg}", sub))
            story.append(Spacer(1, 0.08 * inch))

        story.append(Paragraph(f"<b>Program & Fit Notes:</b> {s['notes']}", sub))

        players = s.get("roster_2026", [])
        if players:
            story.append(PageBreak())
            story.append(Paragraph(s["name"], heading))
            story.append(Spacer(1, 0.05 * inch))
            story.append(Paragraph(
                "Projected 2026 Roster Snapshot (key contributors)",
                roster_heading,
            ))
            story.append(Spacer(1, 0.05 * inch))

            data = [["Name", "Class", "Pos", "Height", "Kills", "Assists", "Digs"]]
            for p in players:
                data.append([
                    p.get("name", ""),
                    p.get("class", ""),
                    p.get("position", ""),
                    p.get("height", ""),
                    p.get("kills", ""),
                    p.get("assists", ""),
                    p.get("digs", ""),
                ])

            roster_table = Table(
                data,
                colWidths=[1.8*inch, 0.65*inch, 0.7*inch, 0.7*inch, 0.75*inch, 0.8*inch, 0.7*inch],
                hAlign="CENTER",
            )
            roster_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("ALIGN", (0, 1), (0, -1), "LEFT"),
                ("ALIGN", (1, 1), (-1, -1), "CENTER"),
            ]))
            story.append(roster_table)

        add_notes_page(s["name"])


__all__ = [
    "build_cover_page",
    "build_map_page",
    "build_fit_score_table",
    "build_travel_matrix",
    "build_school_pages",
]
