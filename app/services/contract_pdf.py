"""Gera o PDF do contrato (reportlab), com a identidade visual da EMG na capa/cabeçalho."""
from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from ..config import BASE_DIR, settings
from ..utils import fmt_date, today_local
from . import contract_text as ct

NAVY = colors.HexColor("#0D1724")
PANEL = colors.HexColor("#142234")
GOLD = colors.HexColor("#C9A45E")
OFFWHITE = colors.HexColor("#EFEBE2")
GREY = colors.HexColor("#A4AAB2")

FONT = "Helvetica"
FONT_B = "Helvetica-Bold"
FONT_T = "Times-Bold"


def _register_fonts() -> None:
    """Usa Jost / Cormorant Garamond se os .ttf estiverem em app/static/fonts; senão, fontes padrão."""
    global FONT, FONT_B, FONT_T
    fdir = BASE_DIR / "app" / "static" / "fonts"
    try:
        if (fdir / "Jost-Regular.ttf").exists() and (fdir / "Jost-Bold.ttf").exists():
            pdfmetrics.registerFont(TTFont("Jost", str(fdir / "Jost-Regular.ttf")))
            pdfmetrics.registerFont(TTFont("Jost-Bold", str(fdir / "Jost-Bold.ttf")))
            FONT, FONT_B = "Jost", "Jost-Bold"
        if (fdir / "CormorantGaramond-Bold.ttf").exists():
            pdfmetrics.registerFont(TTFont("Cormorant-Bold", str(fdir / "CormorantGaramond-Bold.ttf")))
            FONT_T = "Cormorant-Bold"
    except Exception:  # noqa: BLE001
        pass


_register_fonts()


def _styles():
    ss = getSampleStyleSheet()
    return {
        "body": ParagraphStyle("body", parent=ss["Normal"], fontName=FONT, fontSize=9.5, leading=13.5,
                               alignment=TA_JUSTIFY, spaceAfter=5),
        "h": ParagraphStyle("h", parent=ss["Normal"], fontName=FONT_B, fontSize=10.5, leading=14, textColor=NAVY,
                            spaceBefore=10, spaceAfter=5),
        "title": ParagraphStyle("title", parent=ss["Normal"], fontName=FONT_T, fontSize=17, leading=21,
                                textColor=OFFWHITE, alignment=TA_CENTER),
        "subtitle": ParagraphStyle("subtitle", parent=ss["Normal"], fontName=FONT, fontSize=9, leading=12,
                                   textColor=GOLD, alignment=TA_CENTER),
        "small": ParagraphStyle("small", parent=ss["Normal"], fontName=FONT, fontSize=8, leading=11, textColor=GREY),
        "cell": ParagraphStyle("cell", parent=ss["Normal"], fontName=FONT, fontSize=9, leading=12),
        "cellb": ParagraphStyle("cellb", parent=ss["Normal"], fontName=FONT_B, fontSize=9, leading=12),
        "center": ParagraphStyle("center", parent=ss["Normal"], fontName=FONT, fontSize=9.5, leading=13,
                                 alignment=TA_CENTER),
    }


def _header_footer(canvas, doc):
    canvas.saveState()
    w, h = A4
    canvas.setFillColor(NAVY)
    canvas.rect(0, h - 14 * mm, w, 14 * mm, fill=1, stroke=0)
    canvas.setFillColor(GOLD)
    canvas.setFont(FONT_B, 9)
    canvas.drawString(18 * mm, h - 9 * mm, settings.EMG_RAZAO)
    canvas.setFillColor(OFFWHITE)
    canvas.setFont(FONT, 8)
    canvas.drawRightString(w - 18 * mm, h - 9 * mm, f"{settings.EMG_FANTASIA}  |  CNPJ {settings.EMG_CNPJ}")
    canvas.setStrokeColor(GOLD)
    canvas.setLineWidth(0.6)
    canvas.line(18 * mm, 14 * mm, w - 18 * mm, 14 * mm)
    canvas.setFillColor(GREY)
    canvas.setFont(FONT, 7.5)
    canvas.drawString(18 * mm, 9 * mm, "Contrato de Prestação de Serviços de Consultoria Financeira")
    canvas.drawRightString(w - 18 * mm, 9 * mm, f"Página {doc.page}")
    canvas.restoreState()


def _kv_table(rows: list[tuple[str, str]], st) -> Table:
    data = [[Paragraph(k, st["cellb"]), Paragraph(v or "", st["cell"])] for k, v in rows]
    t = Table(data, colWidths=[48 * mm, 122 * mm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#D9D4C7")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3), ("TOPPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def gerar_pdf(contract, destino: Path) -> Path:
    st = _styles()
    destino.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(destino), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=22 * mm, bottomMargin=20 * mm,
                            title=f"Contrato de Consultoria de Crédito - {contract.razao_social}",
                            author=settings.EMG_RAZAO)
    el = []

    # faixa de título
    banner = Table([[Paragraph(ct.TITULO, st["title"])], [Paragraph(ct.SUBTITULO, st["subtitle"])]],
                   colWidths=[170 * mm])
    banner.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PANEL), ("TOPPADDING", (0, 0), (-1, 0), 10),
                                ("BOTTOMPADDING", (0, -1), (-1, -1), 10), ("LEFTPADDING", (0, 0), (-1, -1), 12),
                                ("RIGHTPADDING", (0, 0), (-1, -1), 12)]))
    el += [banner, Spacer(1, 8)]

    el.append(Paragraph("QUALIFICAÇÃO DAS PARTES", st["h"]))
    el.append(Paragraph("CONTRATADA", st["cellb"]))
    el.append(_kv_table(ct.qualificacao_contratada(), st))
    el.append(Spacer(1, 6))
    el.append(Paragraph("CONTRATANTE (CLIENTE)", st["cellb"]))
    el.append(_kv_table(ct.qualificacao_contratante(contract), st))
    el.append(Spacer(1, 8))
    el.append(Paragraph("As partes acima qualificadas celebram o presente Contrato de Prestação de Serviços de "
                        "Consultoria Financeira, que se regerá pelas cláusulas e condições a seguir, as quais declaram "
                        "conhecer e aceitar integralmente.", st["body"]))

    for titulo, paragrafos in ct.clausulas(contract):
        bloco = [Paragraph(titulo, st["h"])]
        for p in paragrafos:
            if p == "__TABELA_EXITO__":
                data = [[Paragraph("VALOR DO CRÉDITO LIBERADO", st["cellb"]), Paragraph("HONORÁRIOS", st["cellb"])]]
                data += [[Paragraph(a, st["cell"]), Paragraph(b, st["cell"])] for a, b in ct.TABELA_EXITO]
                t = Table(data, colWidths=[95 * mm, 75 * mm])
                t.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), OFFWHITE),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#C8C3B6")),
                    ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]))
                bloco += [t, Spacer(1, 5)]
            else:
                bloco.append(Paragraph(p, st["body"]))
        el.append(KeepTogether(bloco[:2]))
        el += bloco[2:]

    el.append(Spacer(1, 10))
    el.append(Paragraph(f"Recife/PE, {fmt_date(today_local())}.", st["center"]))
    el.append(Spacer(1, 22))
    assin = Table([
        [Paragraph("______________________________________", st["center"]),
         Paragraph("______________________________________", st["center"])],
        [Paragraph(f"<b>{settings.EMG_RAZAO}</b><br/>CONTRATADA<br/>{settings.EMG_REPRESENTANTE}, Representante Legal"
                   f"<br/>CPF {settings.EMG_REPRESENTANTE_CPF}", st["center"]),
         Paragraph(f"<b>{contract.razao_social}</b><br/>CONTRATANTE<br/>{contract.representante}"
                   f"<br/>CPF {contract.representante_cpf}", st["center"])],
    ], colWidths=[85 * mm, 85 * mm])
    assin.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    el.append(KeepTogether([assin, Spacer(1, 10), Paragraph(ct.NOTA_JURIDICA, st["small"])]))

    # Anexo I
    el.append(PageBreak())
    el.append(Paragraph("ANEXO I – REGISTRO DE CRÉDITOS LIBERADOS E HONORÁRIOS DEVIDOS", st["h"]))
    el.append(Paragraph("Preenchido e assinado pelas partes a cada operação de crédito efetivamente liberada, nos termos "
                        "das Cláusulas Terceira, Quarta e Décima Terceira.", st["body"]))
    head = ["Data", "Instituição", "Modalidade", "Valor liberado", "Honorários (%)", "Honorários (R$)", "Vencimento"]
    data = [[Paragraph(h, st["cellb"]) for h in head]] + [[""] * 7 for _ in range(8)]
    t = Table(data, colWidths=[20 * mm, 28 * mm, 30 * mm, 26 * mm, 22 * mm, 26 * mm, 22 * mm], rowHeights=[None] + [9 * mm] * 8)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), OFFWHITE),
                           ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#C8C3B6"))]))
    el += [Spacer(1, 6), t, Spacer(1, 24),
           Table([[Paragraph("______________________________<br/>CONTRATADA", st["center"]),
                   Paragraph("______________________________<br/>CONTRATANTE", st["center"])]],
                 colWidths=[85 * mm, 85 * mm])]

    doc.build(el, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return destino
