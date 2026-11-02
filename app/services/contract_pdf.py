"""Gera o PDF do contrato (reportlab) no layout do modelo padrão da EMG."""
from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..config import BASE_DIR, settings
from ..utils import today_local
from . import contract_text as ct

NAVY = colors.HexColor("#0D1724")
GOLD = colors.HexColor("#B8923F")
OFFWHITE = colors.HexColor("#EFEBE2")
GREY = colors.HexColor("#8A9099")
LINE = colors.HexColor("#C8C3B6")

FONT = "Times-Roman"
FONT_B = "Times-Bold"
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
         "novembro", "dezembro"]


def _register_fonts() -> None:
    """Usa Cormorant Garamond se os .ttf estiverem em app/static/fonts; senão, Times (padrão do PDF)."""
    global FONT, FONT_B
    fdir = BASE_DIR / "app" / "static" / "fonts"
    try:
        if (fdir / "CormorantGaramond-Regular.ttf").exists() and (fdir / "CormorantGaramond-Bold.ttf").exists():
            pdfmetrics.registerFont(TTFont("Cormorant", str(fdir / "CormorantGaramond-Regular.ttf")))
            pdfmetrics.registerFont(TTFont("Cormorant-Bold", str(fdir / "CormorantGaramond-Bold.ttf")))
            from reportlab.pdfbase.pdfmetrics import registerFontFamily
            registerFontFamily("Cormorant", normal="Cormorant", bold="Cormorant-Bold", italic="Cormorant",
                               boldItalic="Cormorant-Bold")
            FONT, FONT_B = "Cormorant", "Cormorant-Bold"
    except Exception:  # noqa: BLE001
        pass


_register_fonts()


def _styles():
    ss = getSampleStyleSheet()
    return {
        "body": ParagraphStyle("body", parent=ss["Normal"], fontName=FONT, fontSize=10.5, leading=14.5,
                               alignment=TA_JUSTIFY, spaceAfter=6),
        "h": ParagraphStyle("h", parent=ss["Normal"], fontName=FONT_B, fontSize=11, leading=14, textColor=GOLD,
                            spaceBefore=10, spaceAfter=5),
        "title": ParagraphStyle("title", parent=ss["Normal"], fontName=FONT_B, fontSize=14, leading=18,
                                textColor=NAVY, alignment=TA_CENTER, spaceAfter=14),
        "cell": ParagraphStyle("cell", parent=ss["Normal"], fontName=FONT, fontSize=10, leading=13),
        "cellb": ParagraphStyle("cellb", parent=ss["Normal"], fontName=FONT_B, fontSize=10, leading=13),
        "center": ParagraphStyle("center", parent=ss["Normal"], fontName=FONT, fontSize=10, leading=13,
                                 alignment=TA_CENTER),
        "small": ParagraphStyle("small", parent=ss["Normal"], fontName=FONT, fontSize=8, leading=10, textColor=GREY),
    }


def _header_footer(canvas, doc):
    canvas.saveState()
    w, h = A4
    canvas.setStrokeColor(GOLD)
    canvas.setLineWidth(0.8)
    canvas.line(20 * mm, h - 15 * mm, w - 20 * mm, h - 15 * mm)
    canvas.setFillColor(NAVY)
    canvas.setFont(FONT_B, 9)
    canvas.drawString(20 * mm, h - 12 * mm, settings.EMG_RAZAO)
    canvas.setFillColor(GREY)
    canvas.setFont(FONT, 8.5)
    canvas.drawRightString(w - 20 * mm, h - 12 * mm, f"CNPJ {settings.EMG_CNPJ}")
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.4)
    canvas.line(20 * mm, 14 * mm, w - 20 * mm, 14 * mm)
    canvas.setFont(FONT, 8)
    canvas.drawString(20 * mm, 9.5 * mm, "Contrato de Prestação de Serviços de Consultoria para Estruturação e Captação de Crédito")
    canvas.drawRightString(w - 20 * mm, 9.5 * mm, f"Página {doc.page}")
    canvas.restoreState()


def gerar_pdf(contract, destino: Path) -> Path:
    st = _styles()
    destino.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(destino), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=24 * mm, bottomMargin=20 * mm,
                            title=f"Contrato de Consultoria de Crédito - {contract.razao_social}",
                            author=settings.EMG_RAZAO)
    el = [Paragraph(ct.TITULO, st["title"]), Paragraph(ct.preambulo(contract), st["body"])]

    for titulo, paragrafos in ct.clausulas(contract):
        bloco = [Paragraph(titulo, st["h"])]
        for p in paragrafos:
            if p == "__TABELA_EXITO__":
                data = [[Paragraph("Faixa do valor liberado", st["cellb"]), Paragraph("Honorário de êxito", st["cellb"])]]
                data += [[Paragraph(a, st["cell"]), Paragraph(b, st["cell"])] for a, b in ct.TABELA_EXITO]
                t = Table(data, colWidths=[95 * mm, 75 * mm])
                t.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), OFFWHITE),
                    ("GRID", (0, 0), (-1, -1), 0.5, LINE),
                    ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]))
                bloco += [t, Spacer(1, 6)]
            else:
                bloco.append(Paragraph(p, st["body"]))
        el.append(KeepTogether(bloco[:2]))
        el += bloco[2:]

    hoje = today_local()
    qual = [Paragraph("QUALIFICAÇÃO DA CONTRATANTE", st["h"])]
    qual += [Paragraph(linha, st["body"]) for linha in ct.qualificacao_contratante(contract)]
    qual += [Spacer(1, 10), Paragraph(f"Recife/PE, {hoje.day} de {MESES[hoje.month - 1]} de {hoje.year}.", st["center"]),
             Spacer(1, 26)]
    assin = Table([
        [Paragraph("_________________________________________", st["center"])],
        [Paragraph(f"<b>{settings.EMG_RAZAO}</b><br/>CONTRATADA · assinado eletronicamente", st["center"])],
        [Spacer(1, 26)],
        [Paragraph("_________________________________________", st["center"])],
        [Paragraph(f"<b>{ct._nome_contratante(contract)}</b><br/>CONTRATANTE · {contract.representante} · assinado eletronicamente",
                   st["center"])],
    ], colWidths=[170 * mm])
    el.append(KeepTogether(qual + [assin]))

    doc.build(el, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return destino
