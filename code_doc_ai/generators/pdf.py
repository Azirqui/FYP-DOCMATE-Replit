from __future__ import annotations

import io
import re
from typing import Dict, Any, List, Optional
from datetime import datetime

from fpdf import FPDF


BLUE_PRIMARY = (41, 98, 255)
BLUE_DARK = (25, 42, 86)
GRAY_DARK = (33, 37, 41)
GRAY_MED = (73, 80, 87)
GRAY_LIGHT = (108, 117, 125)
GRAY_BG = (245, 247, 250)
GRAY_BORDER = (200, 200, 200)
TABLE_HEADER_BG = (41, 98, 255)
TABLE_ALT_BG = (245, 247, 250)
WHITE = (255, 255, 255)


class DocPDF(FPDF):
    def __init__(self, project_name: str = "Project"):
        super().__init__()
        self.project_name = project_name
        self.set_auto_page_break(auto=True, margin=25)
        self.toc_entries: List[dict] = []

    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*GRAY_LIGHT)
        self.cell(0, 8, f"{self.project_name} Documentation", align="L")
        self.cell(0, 8, f"Generated {datetime.utcnow().strftime('%B %d, %Y')}", align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*GRAY_BORDER)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*GRAY_LIGHT)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

    def add_cover_page(self, title: str, subtitle: str = "", metrics: Optional[Dict] = None):
        self.add_page()

        self.set_fill_color(*BLUE_DARK)
        self.rect(0, 0, 210, 100, "F")

        self.ln(25)
        self.set_font("Helvetica", "B", 32)
        self.set_text_color(*WHITE)
        safe_title = title.encode('latin-1', 'replace').decode('latin-1')
        self.cell(0, 14, safe_title, align="C", new_x="LMARGIN", new_y="NEXT")

        if subtitle:
            self.ln(4)
            self.set_font("Helvetica", "", 16)
            self.set_text_color(200, 210, 255)
            self.cell(0, 10, subtitle, align="C", new_x="LMARGIN", new_y="NEXT")

        self.ln(4)
        self.set_font("Helvetica", "I", 11)
        self.set_text_color(180, 190, 230)
        self.cell(0, 8, f"Generated on {datetime.utcnow().strftime('%B %d, %Y at %H:%M UTC')}", align="C", new_x="LMARGIN", new_y="NEXT")

        self.set_y(115)

        if metrics:
            self.set_font("Helvetica", "B", 16)
            self.set_text_color(*BLUE_DARK)
            self.cell(0, 12, "Project Summary", align="C", new_x="LMARGIN", new_y="NEXT")
            self.ln(8)

            metric_items = list(metrics.items())
            col_width = 60
            start_x = (210 - col_width * 3) / 2

            for i, (key, value) in enumerate(metric_items):
                col = i % 3
                if i > 0 and col == 0:
                    self.ln(30)

                x = start_x + col * col_width
                y = self.get_y()

                self.set_xy(x, y)
                self.set_font("Helvetica", "B", 22)
                self.set_text_color(*BLUE_PRIMARY)
                self.cell(col_width, 12, str(value), align="C", new_x="LMARGIN", new_y="NEXT")

                self.set_xy(x, y + 13)
                self.set_font("Helvetica", "", 9)
                self.set_text_color(*GRAY_MED)
                label = key.replace("_", " ").title()
                self.cell(col_width, 6, label, align="C")

            remaining = len(metric_items) % 3
            if remaining != 0 or len(metric_items) > 0:
                self.ln(35)

    def add_toc_entry(self, title: str, level: int = 1):
        self.toc_entries.append({
            "title": title,
            "level": level,
            "page": self.page_no(),
        })

    def add_toc_page(self):
        self.add_page()
        self.set_font("Helvetica", "B", 22)
        self.set_text_color(*BLUE_DARK)
        self.cell(0, 12, "Table of Contents", new_x="LMARGIN", new_y="NEXT")
        self.ln(4)
        self.set_draw_color(*BLUE_PRIMARY)
        self.set_line_width(0.8)
        self.line(10, self.get_y(), 60, self.get_y())
        self.set_line_width(0.2)
        self.ln(8)

        for entry in self.toc_entries:
            indent = (entry["level"] - 1) * 8
            if entry["level"] == 1:
                self.set_font("Helvetica", "B", 11)
                self.set_text_color(*GRAY_DARK)
            else:
                self.set_font("Helvetica", "", 10)
                self.set_text_color(*GRAY_MED)

            self.set_x(15 + indent)
            title = entry["title"]
            page = str(entry["page"])
            safe_title = title.encode('latin-1', 'replace').decode('latin-1')

            title_w = self.get_string_width(safe_title)
            page_w = self.get_string_width(page)
            available = 190 - indent - title_w - page_w - 5

            self.cell(title_w + 2, 7, safe_title)
            if available > 10:
                dot_w = self.get_string_width(".")
                num_dots = int(available / dot_w)
                dots = "." * num_dots
                self.set_text_color(*GRAY_BORDER)
                self.cell(available, 7, dots)
            self.set_text_color(*BLUE_PRIMARY)
            self.cell(page_w + 3, 7, page, new_x="LMARGIN", new_y="NEXT")
            self.ln(1)

    def add_section(self, title: str, level: int = 1, add_to_toc: bool = True):
        if self.get_y() > 250:
            self.add_page()

        if add_to_toc:
            self.add_toc_entry(title, level)

        self.ln(4)
        if level == 1:
            self.set_font("Helvetica", "B", 20)
            self.set_text_color(*BLUE_DARK)
            safe_title = title.encode('latin-1', 'replace').decode('latin-1')
            self.cell(0, 12, safe_title, new_x="LMARGIN", new_y="NEXT")
            self.set_draw_color(*BLUE_PRIMARY)
            self.set_line_width(0.8)
            self.line(10, self.get_y(), 60, self.get_y())
            self.set_line_width(0.2)
        elif level == 2:
            self.set_font("Helvetica", "B", 15)
            self.set_text_color(*GRAY_DARK)
            safe_title = title.encode('latin-1', 'replace').decode('latin-1')
            self.cell(0, 10, safe_title, new_x="LMARGIN", new_y="NEXT")
            self.set_draw_color(*GRAY_BORDER)
            self.line(10, self.get_y(), 200, self.get_y())
        else:
            self.set_font("Helvetica", "B", 12)
            self.set_text_color(*GRAY_MED)
            safe_title = title.encode('latin-1', 'replace').decode('latin-1')
            self.cell(0, 8, safe_title, new_x="LMARGIN", new_y="NEXT")

        self.ln(4)

    def add_markdown_text(self, text: str):
        self.set_text_color(*GRAY_DARK)
        lines = text.split("\n")
        in_code_block = False

        for line in lines:
            if self.get_y() > 265:
                self.add_page()

            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                if in_code_block:
                    self.ln(3)
                else:
                    self.ln(3)
                continue

            if in_code_block:
                self.set_fill_color(*GRAY_BG)
                self.set_font("Courier", "", 8)
                self.set_text_color(*GRAY_DARK)
                safe_line = line.encode('latin-1', 'replace').decode('latin-1')
                self.cell(0, 4.5, f"  {safe_line}", fill=True, new_x="LMARGIN", new_y="NEXT")
                continue

            if line.startswith("# "):
                self.add_section(line[2:], 1, add_to_toc=False)
            elif line.startswith("## "):
                self.add_section(line[3:], 2, add_to_toc=False)
            elif line.startswith("### "):
                self.add_section(line[4:], 3, add_to_toc=False)
            elif line.startswith("- ") or line.startswith("* "):
                self.set_font("Helvetica", "", 10)
                self.set_text_color(*GRAY_DARK)
                bullet_text = line[2:].strip()
                clean = re.sub(r'\*\*(.*?)\*\*', r'\1', bullet_text)
                safe_text = clean.encode('latin-1', 'replace').decode('latin-1')
                self.cell(8, 6, "-")
                self.multi_cell(0, 6, safe_text, new_x="LMARGIN", new_y="NEXT")
            elif line.strip() == "":
                self.ln(3)
            else:
                self.set_font("Helvetica", "", 10)
                self.set_text_color(*GRAY_DARK)
                clean = re.sub(r'\*\*(.*?)\*\*', r'\1', line)
                clean = re.sub(r'\*(.*?)\*', r'\1', clean)
                safe_text = clean.encode('latin-1', 'replace').decode('latin-1')
                self.multi_cell(0, 6, safe_text, new_x="LMARGIN", new_y="NEXT")

    def add_code_block(self, code: str, title: str = ""):
        if title:
            self.set_font("Helvetica", "B", 10)
            self.set_text_color(*GRAY_MED)
            safe_title = title.encode('latin-1', 'replace').decode('latin-1')
            self.cell(0, 8, safe_title, new_x="LMARGIN", new_y="NEXT")

        self.ln(2)
        self.set_fill_color(*GRAY_BG)
        self.set_draw_color(*GRAY_BORDER)
        self.set_font("Courier", "", 8)
        self.set_text_color(*GRAY_DARK)

        code_lines = code.split("\n")
        start_y = self.get_y()

        for i, line in enumerate(code_lines):
            if self.get_y() > 265:
                self.add_page()
                start_y = self.get_y()

            safe_line = line.encode('latin-1', 'replace').decode('latin-1')

            self.set_font("Courier", "", 7)
            self.set_text_color(*GRAY_LIGHT)
            self.cell(10, 4.5, str(i + 1).rjust(3), fill=True)

            self.set_font("Courier", "", 8)
            self.set_text_color(*GRAY_DARK)
            self.cell(0, 4.5, f" {safe_line}", fill=True, new_x="LMARGIN", new_y="NEXT")

        self.ln(4)

    def add_info_box(self, text: str, box_type: str = "info"):
        if box_type == "info":
            bg = (235, 245, 255)
            border_color = BLUE_PRIMARY
            text_color = BLUE_DARK
        elif box_type == "warning":
            bg = (255, 248, 235)
            border_color = (255, 165, 0)
            text_color = (140, 90, 0)
        else:
            bg = GRAY_BG
            border_color = GRAY_BORDER
            text_color = GRAY_DARK

        self.set_fill_color(*bg)
        self.set_draw_color(*border_color)
        y = self.get_y()
        self.rect(12, y, 186, 12, "FD")
        self.set_xy(16, y + 2)
        self.set_font("Helvetica", "I", 9)
        self.set_text_color(*text_color)
        safe_text = text.encode('latin-1', 'replace').decode('latin-1')
        self.multi_cell(178, 5, safe_text)
        self.ln(4)

    def add_class_detail(self, cls_data: Dict):
        name = cls_data.get("name", "")
        methods = cls_data.get("methods", [])
        attrs = cls_data.get("attributes", [])
        bases = cls_data.get("base_classes", [])
        description = cls_data.get("description", "")

        if self.get_y() > 240:
            self.add_page()

        self.set_fill_color(*GRAY_BG)
        self.set_draw_color(*BLUE_PRIMARY)

        y = self.get_y()
        self.rect(10, y, 190, 10, "FD")
        self.set_xy(14, y + 2)
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(*BLUE_DARK)
        safe_name = name.encode('latin-1', 'replace').decode('latin-1')
        self.cell(0, 6, safe_name)
        if bases:
            self.set_font("Helvetica", "I", 10)
            self.set_text_color(*GRAY_LIGHT)
            bases_str = f"  extends {', '.join(bases)}"
            safe_bases = bases_str.encode('latin-1', 'replace').decode('latin-1')
            self.cell(0, 6, safe_bases)
        self.ln(12)

        if description:
            self.set_font("Helvetica", "I", 10)
            self.set_text_color(*GRAY_MED)
            safe_desc = description.encode('latin-1', 'replace').decode('latin-1')
            self.multi_cell(0, 5, safe_desc, new_x="LMARGIN", new_y="NEXT")
            self.ln(3)

        if attrs:
            self.set_font("Helvetica", "B", 10)
            self.set_text_color(*GRAY_DARK)
            self.cell(0, 7, "Attributes", new_x="LMARGIN", new_y="NEXT")

            self.set_fill_color(*TABLE_HEADER_BG)
            self.set_font("Helvetica", "B", 9)
            self.set_text_color(*WHITE)
            self.cell(60, 7, "  Name", fill=True, border=1)
            self.cell(130, 7, "  Type", fill=True, border=1, new_x="LMARGIN", new_y="NEXT")

            self.set_font("Helvetica", "", 9)
            for i, attr in enumerate(attrs):
                if self.get_y() > 265:
                    self.add_page()
                if i % 2 == 0:
                    self.set_fill_color(*TABLE_ALT_BG)
                else:
                    self.set_fill_color(*WHITE)
                self.set_text_color(*GRAY_DARK)
                attr_name = attr if isinstance(attr, str) else str(attr)
                safe_attr = attr_name.encode('latin-1', 'replace').decode('latin-1')
                self.cell(60, 6, f"  {safe_attr}", fill=True, border=1)
                self.cell(130, 6, "", fill=True, border=1, new_x="LMARGIN", new_y="NEXT")
            self.ln(3)

        if methods:
            self.set_font("Helvetica", "B", 10)
            self.set_text_color(*GRAY_DARK)
            self.cell(0, 7, "Methods", new_x="LMARGIN", new_y="NEXT")

            self.set_fill_color(*TABLE_HEADER_BG)
            self.set_font("Helvetica", "B", 9)
            self.set_text_color(*WHITE)
            self.cell(60, 7, "  Method", fill=True, border=1)
            self.cell(130, 7, "  Visibility", fill=True, border=1, new_x="LMARGIN", new_y="NEXT")

            self.set_font("Helvetica", "", 9)
            for i, method in enumerate(methods):
                if self.get_y() > 265:
                    self.add_page()
                if i % 2 == 0:
                    self.set_fill_color(*TABLE_ALT_BG)
                else:
                    self.set_fill_color(*WHITE)
                self.set_text_color(*GRAY_DARK)
                m_name = method if isinstance(method, str) else str(method)
                safe_m = m_name.encode('latin-1', 'replace').decode('latin-1')
                visibility = "Private" if m_name.startswith("_") and not m_name.startswith("__") else "Public"
                if m_name.startswith("__") and m_name.endswith("__"):
                    visibility = "Special"
                self.cell(60, 6, f"  {safe_m}", fill=True, border=1)
                self.cell(130, 6, f"  {visibility}", fill=True, border=1, new_x="LMARGIN", new_y="NEXT")
            self.ln(3)

        self.ln(4)

    def add_function_detail(self, fn_data: Dict):
        name = fn_data.get("name", "")
        params = fn_data.get("parameters", [])
        ret = fn_data.get("return_type", "")
        description = fn_data.get("description", "")

        if self.get_y() > 250:
            self.add_page()

        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*BLUE_DARK)
        sig = f"{name}("
        if params:
            sig += ", ".join(params[:6])
            if len(params) > 6:
                sig += ", ..."
        sig += ")"
        if ret:
            sig += f" -> {ret}"
        safe_sig = sig.encode('latin-1', 'replace').decode('latin-1')
        self.cell(0, 7, safe_sig, new_x="LMARGIN", new_y="NEXT")

        if description:
            self.set_font("Helvetica", "I", 9)
            self.set_text_color(*GRAY_MED)
            safe_desc = description.encode('latin-1', 'replace').decode('latin-1')
            self.multi_cell(0, 5, safe_desc, new_x="LMARGIN", new_y="NEXT")
            self.ln(2)

        if params:
            self.set_fill_color(*TABLE_HEADER_BG)
            self.set_font("Helvetica", "B", 9)
            self.set_text_color(*WHITE)
            self.cell(60, 6, "  Parameter", fill=True, border=1)
            self.cell(60, 6, "  Type", fill=True, border=1)
            self.cell(70, 6, "  Default", fill=True, border=1, new_x="LMARGIN", new_y="NEXT")

            self.set_font("Helvetica", "", 9)
            for i, p in enumerate(params):
                if self.get_y() > 265:
                    self.add_page()
                if i % 2 == 0:
                    self.set_fill_color(*TABLE_ALT_BG)
                else:
                    self.set_fill_color(*WHITE)
                self.set_text_color(*GRAY_DARK)

                if ": " in p:
                    p_name, p_type = p.split(": ", 1)
                else:
                    p_name, p_type = p, ""

                safe_name = p_name.encode('latin-1', 'replace').decode('latin-1')
                safe_type = p_type.encode('latin-1', 'replace').decode('latin-1')
                self.cell(60, 6, f"  {safe_name}", fill=True, border=1)
                self.cell(60, 6, f"  {safe_type}", fill=True, border=1)
                self.cell(70, 6, "", fill=True, border=1, new_x="LMARGIN", new_y="NEXT")

        if ret:
            self.set_font("Helvetica", "I", 9)
            self.set_text_color(*GRAY_MED)
            safe_ret = ret.encode('latin-1', 'replace').decode('latin-1')
            self.cell(0, 6, f"Returns: {safe_ret}", new_x="LMARGIN", new_y="NEXT")

        self.ln(5)

    def add_file_analysis(self, file_data: Dict):
        path = file_data.get("path", "unknown")
        self.add_section(path, 2)

        classes = file_data.get("classes", [])
        functions = file_data.get("functions", [])

        if not classes and not functions:
            self.set_font("Helvetica", "I", 10)
            self.set_text_color(*GRAY_LIGHT)
            self.cell(0, 6, "No classes or functions found in this file.", new_x="LMARGIN", new_y="NEXT")
            self.ln(4)
            return

        if classes:
            self.add_section("Classes", 3, add_to_toc=False)
            for cls in classes:
                self.add_class_detail(cls)

        if functions:
            self.add_section("Functions", 3, add_to_toc=False)
            for fn in functions:
                self.add_function_detail(fn)

    def add_relationships_table(self, relationships: List):
        if not relationships:
            return

        self.set_fill_color(*TABLE_HEADER_BG)
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*WHITE)
        self.cell(48, 8, "  From", fill=True, border=1)
        self.cell(48, 8, "  To", fill=True, border=1)
        self.cell(48, 8, "  Type", fill=True, border=1)
        self.cell(46, 8, "  Description", fill=True, border=1, new_x="LMARGIN", new_y="NEXT")

        self.set_font("Helvetica", "", 9)
        for i, rel in enumerate(relationships):
            if self.get_y() > 265:
                self.add_page()

            if isinstance(rel, dict):
                from_e = rel.get("from_entity", "")
                to_e = rel.get("to_entity", "")
                rel_type = rel.get("relationship_type", "")
                label = rel.get("label", "")
            else:
                from_e = getattr(rel, "from_entity", "")
                to_e = getattr(rel, "to_entity", "")
                rel_type = getattr(rel, "relationship_type", "")
                label = getattr(rel, "label", "") or ""

            if i % 2 == 0:
                self.set_fill_color(*TABLE_ALT_BG)
            else:
                self.set_fill_color(*WHITE)

            self.set_text_color(*GRAY_DARK)
            self.cell(48, 7, f"  {from_e}", fill=True, border=1)
            self.cell(48, 7, f"  {to_e}", fill=True, border=1)

            type_colors = {
                "inheritance": BLUE_PRIMARY,
                "composition": (40, 167, 69),
                "dependency": (255, 165, 0),
            }
            type_color = type_colors.get(rel_type, GRAY_DARK)
            self.set_text_color(*type_color)
            self.set_font("Helvetica", "B", 9)
            self.cell(48, 7, f"  {rel_type}", fill=True, border=1)

            self.set_text_color(*GRAY_DARK)
            self.set_font("Helvetica", "", 9)
            self.cell(46, 7, f"  {label}", fill=True, border=1, new_x="LMARGIN", new_y="NEXT")


def generate_pdf(
    project_name: str = "Project",
    analysis: Optional[Dict[str, Any]] = None,
    uml: Optional[Dict[str, str]] = None,
    documentation: Optional[str] = None,
    module_docs: Optional[Dict[str, str]] = None,
    relationships: Optional[List] = None,
    metrics: Optional[Dict[str, Any]] = None,
) -> bytes:
    pdf = DocPDF(project_name=project_name)
    pdf.alias_nb_pages()

    effective_metrics = metrics
    if not effective_metrics and analysis:
        effective_metrics = analysis.get("metrics")

    pdf.add_cover_page(
        title=project_name,
        subtitle="Code Documentation",
        metrics=effective_metrics,
    )

    if documentation:
        pdf.add_page()
        pdf.add_section("Project Overview", 1)
        pdf.add_info_box("This section was generated using AI-powered analysis.", "info")
        pdf.add_markdown_text(documentation)

    if module_docs:
        pdf.add_page()
        pdf.add_section("Module Documentation", 1)
        pdf.add_info_box("AI-generated documentation for each module in the project.", "info")
        for module_path, doc_text in module_docs.items():
            pdf.add_section(module_path, 2)
            pdf.add_markdown_text(doc_text)

    if analysis and analysis.get("files"):
        pdf.add_page()
        pdf.add_section("File Analysis", 1)
        if not documentation:
            pdf.add_info_box(
                "Tip: Provide an LLM API key (X-API-Key header) to get AI-generated descriptions for each class and function.",
                "warning"
            )
        for file_data in analysis["files"]:
            pdf.add_file_analysis(file_data)

    if uml:
        pdf.add_page()
        pdf.add_section("UML Diagrams", 1)
        pdf.add_info_box("Render these Mermaid diagrams at mermaid.live or in any Mermaid-compatible viewer.", "info")

        if uml.get("class_diagram"):
            pdf.add_section("Class Diagram", 2)
            pdf.add_code_block(uml["class_diagram"])

        if uml.get("dependency_graph"):
            pdf.add_section("Dependency Graph", 2)
            pdf.add_code_block(uml["dependency_graph"])

        if uml.get("inheritance_diagram"):
            pdf.add_section("Inheritance Diagram", 2)
            pdf.add_code_block(uml["inheritance_diagram"])

    if relationships:
        pdf.add_page()
        pdf.add_section("Class Relationships", 1)
        pdf.add_relationships_table(relationships)

    toc_entries = list(pdf.toc_entries)
    pdf.toc_entries = []

    toc_pdf = DocPDF(project_name=project_name)
    toc_pdf.alias_nb_pages()

    toc_pdf.add_cover_page(
        title=project_name,
        subtitle="Code Documentation",
        metrics=effective_metrics,
    )

    toc_pdf.toc_entries = toc_entries
    toc_pdf.add_toc_page()

    if documentation:
        toc_pdf.add_page()
        toc_pdf.add_section("Project Overview", 1, add_to_toc=False)
        toc_pdf.add_info_box("This section was generated using AI-powered analysis.", "info")
        toc_pdf.add_markdown_text(documentation)

    if module_docs:
        toc_pdf.add_page()
        toc_pdf.add_section("Module Documentation", 1, add_to_toc=False)
        toc_pdf.add_info_box("AI-generated documentation for each module in the project.", "info")
        for module_path, doc_text in module_docs.items():
            toc_pdf.add_section(module_path, 2, add_to_toc=False)
            toc_pdf.add_markdown_text(doc_text)

    if analysis and analysis.get("files"):
        toc_pdf.add_page()
        toc_pdf.add_section("File Analysis", 1, add_to_toc=False)
        if not documentation:
            toc_pdf.add_info_box(
                "Tip: Provide an LLM API key (X-API-Key header) to get AI-generated descriptions for each class and function.",
                "warning"
            )
        for file_data in analysis["files"]:
            toc_pdf.add_file_analysis(file_data)

    if uml:
        toc_pdf.add_page()
        toc_pdf.add_section("UML Diagrams", 1, add_to_toc=False)
        toc_pdf.add_info_box("Render these Mermaid diagrams at mermaid.live or in any Mermaid-compatible viewer.", "info")

        if uml.get("class_diagram"):
            toc_pdf.add_section("Class Diagram", 2, add_to_toc=False)
            toc_pdf.add_code_block(uml["class_diagram"])

        if uml.get("dependency_graph"):
            toc_pdf.add_section("Dependency Graph", 2, add_to_toc=False)
            toc_pdf.add_code_block(uml["dependency_graph"])

        if uml.get("inheritance_diagram"):
            toc_pdf.add_section("Inheritance Diagram", 2, add_to_toc=False)
            toc_pdf.add_code_block(uml["inheritance_diagram"])

    if relationships:
        toc_pdf.add_page()
        toc_pdf.add_section("Class Relationships", 1, add_to_toc=False)
        toc_pdf.add_relationships_table(relationships)

    output = toc_pdf.output()
    return bytes(output) if output else b""
