import os
import sys
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

# Configure stdout
sys.stdout.reconfigure(encoding='utf-8')

# Register Turkish-capable font
font_reg = False
for f_reg, b_reg in [
    ('C:/Windows/Fonts/segoeui.ttf', 'C:/Windows/Fonts/segoeuib.ttf'),
    ('C:/Windows/Fonts/arial.ttf', 'C:/Windows/Fonts/arialbd.ttf'),
]:
    if os.path.exists(f_reg) and os.path.exists(b_reg):
        pdfmetrics.registerFont(TTFont('AppFont', f_reg))
        pdfmetrics.registerFont(TTFont('AppFont-Bold', b_reg))
        font_reg = True
        break

if not font_reg:
    print("Warning: Standard Windows fonts not found, fallback to Helvetica")
    font_name = 'Helvetica'
    font_bold = 'Helvetica-Bold'
else:
    font_name = 'AppFont'
    font_bold = 'AppFont-Bold'

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super(NumberedCanvas, self).showPage()
        super(NumberedCanvas, self).save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        
        # Header (pages > 1)
        if self._pageNumber > 1:
            self.setFont(font_name, 8)
            self.setFillColor(colors.HexColor('#64748b'))
            self.drawString(54, 11 * inch - 36, "UFC ELO RATING & PREDICTIVE ML ENGINE | TOTAL MASTER PLAN")
            self.drawRightString(8.5 * inch - 54, 11 * inch - 36, "LEAD ARCHITECT & DATA SCIENCE SPECIFICATION")
            self.setStrokeColor(colors.HexColor('#cbd5e1'))
            self.setLineWidth(0.5)
            self.line(54, 11 * inch - 42, 8.5 * inch - 54, 11 * inch - 42)

        # Footer
        self.setFont(font_name, 8)
        self.setFillColor(colors.HexColor('#64748b'))
        self.drawString(54, 36, "Gizli & Özel | UFC Quantitative Predictive Analytics & +EV Value Engine")
        page_text = f"Sayfa {self._pageNumber} / {page_count}"
        self.drawRightString(8.5 * inch - 54, 36, page_text)
        self.setStrokeColor(colors.HexColor('#cbd5e1'))
        self.setLineWidth(0.5)
        self.line(54, 46, 8.5 * inch - 54, 46)

        self.restoreState()

def build_pdf(filename="total_master_plan.pdf"):
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()

    # Custom Palette
    C_PRIMARY = colors.HexColor('#0f172a')     # Dark Navy/Slate
    C_ACCENT = colors.HexColor('#e11d48')      # UFC Crimson Red
    C_GOLD = colors.HexColor('#b45309')        # Dark Amber Gold
    C_EMERALD = colors.HexColor('#047857')     # Emerald Green
    C_TEXT = colors.HexColor('#1e293b')        # Body Text
    C_MUTED = colors.HexColor('#475569')       # Muted Grey Text
    C_CARD_BG = colors.HexColor('#f8fafc')     # Light Slate Box
    C_BORDER = colors.HexColor('#e2e8f0')      # Border grey

    # Typography Styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName=font_bold,
        fontSize=22,
        leading=26,
        textColor=C_PRIMARY,
        spaceAfter=4
    )

    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName=font_name,
        fontSize=10,
        leading=14,
        textColor=C_ACCENT,
        spaceAfter=14
    )

    h1_style = ParagraphStyle(
        'Heading1_Custom',
        fontName=font_bold,
        fontSize=13,
        leading=16,
        textColor=C_PRIMARY,
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'Heading2_Custom',
        fontName=font_bold,
        fontSize=10.5,
        leading=14,
        textColor=C_ACCENT,
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'Body_Custom',
        fontName=font_name,
        fontSize=9,
        leading=13,
        textColor=C_TEXT,
        spaceAfter=6
    )

    bullet_style = ParagraphStyle(
        'Bullet_Custom',
        fontName=font_name,
        fontSize=8.8,
        leading=12.5,
        textColor=C_TEXT,
        leftIndent=12,
        spaceAfter=3
    )

    formula_style = ParagraphStyle(
        'Formula_Custom',
        fontName=font_bold,
        fontSize=9,
        leading=13,
        textColor=C_PRIMARY,
        alignment=1
    )

    callout_style = ParagraphStyle(
        'Callout_Custom',
        fontName=font_name,
        fontSize=8.8,
        leading=12.5,
        textColor=C_TEXT
    )

    story = []

    # =========================================================================
    # COVER / HEADER BANNER
    # =========================================================================
    header_data = [
        [
            Paragraph("<b>UFC ELO RATING & VALUE BETTING SYSTEM</b>", title_style),
            Paragraph("<b>MASTER PLAN</b><br/><font color='#e11d48'>v2.4 Production</font>", ParagraphStyle('R_Head', fontName=font_bold, fontSize=11, leading=14, alignment=2, textColor=C_PRIMARY))
        ],
        [
            Paragraph("TOTAL ARCHITECTURAL ROADMAP & QUANTITATIVE SPECIFICATION", subtitle_style),
            Paragraph("Tarih: Ağustos 2026<br/>Baş Mimar & Veri Bilimi Raporu", ParagraphStyle('R_Sub', fontName=font_name, fontSize=8, leading=11, alignment=2, textColor=C_MUTED))
        ]
    ]
    header_table = Table(header_data, colWidths=[360, 144])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(header_table)
    story.append(HRFlowable(width="100%", thickness=2, color=C_ACCENT, spaceBefore=4, spaceAfter=10))

    # =========================================================================
    # SECTION 1: PROJENİN ANA MİSYONU VE HEDEFİ
    # =========================================================================
    story.append(Paragraph("1. Projenin Ana Misyonu ve Stratejik Hedefi", h1_style))
    
    mission_text = (
        "Bu projenin nihai varoluş amacı iki ana sütun üzerine inşa edilmiştir:<br/>"
        "<b>1. Kusursuz Elo & Yetenek Modellemesi:</b> Karma dövüş sanatlarının (MMA/UFC) kaotik ve çok boyutlu doğasını "
        "salt galibiyet/mağlubiyet ötesine geçerek; ayakta vuruş isabeti, güreş kontrolü, kardiyo dayanıklılığı, taktiksel stiller, "
        "yaş/menzil avantajları ve ring pası (inaktivite) gibi mikro parametrelerle akıl almaz bir matematiksel doğrulukla modellemek.<br/>"
        "<b>2. Piyasa Fiyatlama Hatalarını Yakalama (+EV Value Betting):</b> Geliştirilen bu süper-hassas kazanma ihtimallerini, "
        "küresel bahis bürolarının (FanDuel, DraftKings, BetMGM, Bovada vb.) kamuoyu algısı, popülerlik yanlılığı ve eksik veriyle "
        "açtığı bahis oranlarıyla (odds) gerçek zamanlı kıyaslamak; pozitif beklenen değerli (+EV) arbitraj ve değer fırsatlarını "
        "Quarter-Kelly kasa yönetimi disipliniyle net kâra dönüştürmektir."
    )
    
    mission_box = Table([[Paragraph(mission_text, callout_style)]], colWidths=[504])
    mission_box.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#fff1f2')),
        ('BORDER', (0,0), (-1,-1), 1, colors.HexColor('#fecdd3')),
        ('PADDING', (0,0), (-1,-1), 8),
        ('ROUNDEDCORNERS', [4, 4, 4, 4]),
    ]))
    story.append(mission_box)
    story.append(Spacer(1, 8))

    # =========================================================================
    # SECTION 2: MEVCUT MİMARİ VE VERİ HATTI (PIPELINE)
    # =========================================================================
    story.append(Paragraph("2. Mevcut Mimari: Veri Hattı, İşleme ve Elo Motoru", h1_style))
    story.append(Paragraph(
        "Sistemimiz, UFC'nin 1993'teki ilk etkinliğinden (UFC 1) günümüze kadar gerçekleşen tüm müsabakaları uçtan uca işleyen "
        "tam entegre bir veri bilimi boru hattına (pipeline) sahiptir:", body_style
    ))

    arch_items = [
        "<b>Scraper & Crawler Modülü:</b> UFCStats ve resmi kaynaklardan <b>8,515+ profesyonel maç</b> ve <b>2,540+ dövüşçünün</b> "
        "tüm kariyer kayıtlarını (vuruş sayıları, isabet yüzdeleri, takedownlar, kontrol süreleri, nakavt/pes ettirme detayları) otomatik olarak çeker.",
        
        "<b>Veri Temizleme & Biyometrik Entegratör:</b> Dövüşçü isim eşleştirmeleri, unvan maçı tespitleri, duruş (Ortodoks/Southpaw/Switch), "
        "boy, menzil, yaş farkı ve kilo sınıfı normalizasyonu yapar. Eksik veriler sıklet medyanları ile doldurulur.",
        
        "<b>3D Bileşen Elo Motoru (Striking, Grappling, Cardio):</b> Her dövüşçüye tek bir genel puan yerine 3 farklı boyutta bağımsız "
        "Elo puanı atanır. Vuruşçunun vuruşçuya karşı üstünlüğü ile güreşçiye karşı dayanıklılığı ayrıştırılır.",
        
        "<b>Taktiksel Stil Matrisi (6 Temel Arketip):</b> Dövüşçüler <i>Distance Out-Fighter, Pressure Brawler, Power Counter-Striker, "
        "Pressure Wrestler, Submission Grappler</i> ve <i>Balanced Hybrid</i> olarak sınıflandırılır ve stiller arası avantaj matrisi işletilir.",
        
        "<b>Inactivity Elo Decay (-5/ay) & Glicko Comeback Volatilitesi:</b> 18 aydan uzun süre kafese çıkmayan dövüşçülerde yaş ve form kaybı "
        "otomatik puan düşüşüyle cezalandırılır; dönüş maçlarında ise K-Faktörü 1.0x-1.6x aralığında esnetilerek belirsizlik fiyatlanır.",
        
        "<b>Pedigree Anchor Sistemi:</b> D1 NCAA güreş şampiyonları veya ADCC grapplerları gibi elit atletler (örn. Bo Nickal, Gable Steveson) "
        "UFC'ye ilk adımlarında 1500 yerine 1650-1820 bandında başlangıç puanı ile sabitlenir."
    ]
    for item in arch_items:
        story.append(Paragraph(f"• {item}", bullet_style))
    
    story.append(Spacer(1, 8))

    # =========================================================================
    # SECTION 3: ELO ALGORİTMASI VE MATEMATİKSEL ÇARPANLAR
    # =========================================================================
    story.append(Paragraph("3. Elo Algoritması: Matematiksel Formülasyonlar ve Çarpanlar", h1_style))
    story.append(Paragraph(
        "Geleneksel satranç Elo formülü MMA için yetersizdir. Sistemimiz dövüşün nasıl kazanıldığını ve maç içi üstünlüğü "
        "aşağıdaki dinamik formülasyonla derecelendirir:", body_style
    ))

    # Table of Multipliers
    formula_data = [
        [
            Paragraph("<b>Bileşen / Faktör</b>", ParagraphStyle('TH', fontName=font_bold, fontSize=8, textColor=colors.white)),
            Paragraph("<b>Uygulanan Formül / Çarpan</b>", ParagraphStyle('TH', fontName=font_bold, fontSize=8, textColor=colors.white)),
            Paragraph("<b>Stratejik Etki & Açıklama</b>", ParagraphStyle('TH', fontName=font_bold, fontSize=8, textColor=colors.white))
        ],
        [
            Paragraph("<b>In-Fight Dominance ($D$)</b>", body_style),
            Paragraph("$$D = W \\pm (0.25 \\cdot KD + 0.005 \\cdot \\Delta Str + 0.05 \\cdot \\Delta Ctrl)$$", formula_style),
            Paragraph("Tek taraflı dayak atan dövüşçü şans eseri kazanan dövüşçüden çok daha yüksek Elo kazanır.", body_style)
        ],
        [
            Paragraph("<b>Bitiş Türü Çarpanı ($M_{finish}$)</b>", body_style),
            Paragraph("<b>R1 KO/Sub: 1.25x | Decision: 0.85x | Split: 0.70x</b>", formula_style),
            Paragraph("İlk rauntta gelen net nakavtlar tam K-faktörü alırken, tartışmalı kararlar kısıtlanır.", body_style)
        ],
        [
            Paragraph("<b>Unvan Maçı (Title Bout)</b>", body_style),
            Paragraph("<b>K-Faktörü Ağırlığı: +20% (1.20x)</b>", formula_style),
            Paragraph("5 rauntluk şampiyonluk maçları dövüşçü kalitesini en net belirleyen elit arenadır.", body_style)
        ],
        [
            Paragraph("<b>Yaş Uçurumu (Age Cliff)</b>", body_style),
            Paragraph("<b>Yaş &gt; 35 ise: Yıl başına -12.5 Elo Düzeltmesi</b>", formula_style),
            Paragraph("Hafif sıkletlerde 35+ yaş dövüşçülerin reaksiyon ve çene dayanıklılığı düşüşü fiyatlanır.", body_style)
        ],
        [
            Paragraph("<b>Kafes & İrtifa Etkisi</b>", body_style),
            Paragraph("<b>25-ft Apex: Güreşçi +15 | İrtifa &gt;4000ft: Kardiyo 1.4x</b>", formula_style),
            Paragraph("Küçük kafes baskı güreşçilerine yarar; Utah/Denver gibi irtifalarda kardiyo açığı ölümcüldür.", body_style)
        ]
    ]

    formula_table = Table(formula_data, colWidths=[120, 180, 204])
    formula_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), C_PRIMARY),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, C_BORDER),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, C_CARD_BG]),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(formula_table)
    story.append(Spacer(1, 10))

    # =========================================================================
    # SECTION 4: VALUE BET MANTIĞI VE KANTİTATİF BAHİS TEORİSİ
    # =========================================================================
    story.append(Paragraph("4. Value Bet Mantığı: Gerçek Olasılık vs Bahis Bürosu Fiyatlaması", h1_style))
    story.append(Paragraph(
        "Bahis piyasasında uzun vadeli kârlılık, kimin kazanacağını tahmin etmekten değil; <b>oranların ima ettiği olasılık ile "
        "modelimizin hesapladığı gerçek olasılık arasındaki matematiksel sapmayı (+EV)</b> bulmaktan geçer.", body_style
    ))

    ev_box_text = (
        "<b>1. İma Edilen Olasılık (Implied Probability):</b> $P_{\\text{implied}} = \\frac{1}{\\text{Ondalık Oran}}$ (Büro kâr marjı arındırılarak)<br/>"
        "<b>2. Beklenen Değer (+EV):</b> $\\text{EV} = [P_{\\text{model}} \\times (\\text{Oran} - 1)] - (1 - P_{\\text{model}})$<br/>"
        "<i>Örnek:</i> Modelimiz Dövüşçü A'ya <b>%62.5</b> şans veriyorken, büro <b>2.10 (+110)</b> oran açmışsa ($P_{\\text{implied}} = \\%47.6$):<br/>"
        "$$\\text{EV} = [0.625 \\times 1.10] - [0.375] = +0.3125 \\rightarrow \\mathbf{+\\%31.25 \\text{ Devasa Value Bet!}}$$<br/>"
        "<b>3. Kasa Yönetimi (Quarter-Kelly Kriteri):</b> Kasa batma riskini (Drawdown) sıfırlamak için tam Kelly yerine çeyrek Kelly kullanılır:<br/>"
        "$$f^* = \\frac{b \\cdot p - q}{b}, \\quad \\text{Bahis Miktarı} = \\frac{1}{4} f^* \\times \\text{Toplam Kasa}$quot;"
    )

    ev_box = Table([[Paragraph(ev_box_text, callout_style)]], colWidths=[504])
    ev_box.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#ecfdf5')),
        ('BORDER', (0,0), (-1,-1), 1, colors.HexColor('#a7f3d0')),
        ('PADDING', (0,0), (-1,-1), 8),
        ('ROUNDEDCORNERS', [4, 4, 4, 4]),
    ]))
    story.append(ev_box)
    story.append(Spacer(1, 10))

    # =========================================================================
    # SECTION 5: GELECEK YOL HARİTASI (FUTURE ROADMAP)
    # =========================================================================
    story.append(Paragraph("5. Gelecek Yol Haritası: Sisteme Eklenecek İleri Düzey Parametreler", h1_style))
    story.append(Paragraph(
        "Kusursuz tahmin oranına ve tam otomatik kâr makinesine ulaşmak için önümüzdeki geliştirme fazlarında "
        "sisteme entegre edilecek 5 kritik modül:", body_style
    ))

    roadmap_data = [
        [
            Paragraph("<b>Faz</b>", ParagraphStyle('TH', fontName=font_bold, fontSize=8, textColor=colors.white)),
            Paragraph("<b>Geliştirilecek Modül & Parametre</b>", ParagraphStyle('TH', fontName=font_bold, fontSize=8, textColor=colors.white)),
            Paragraph("<b>Hedeflenen Katkı & Kârlılık Artışı</b>", ParagraphStyle('TH', fontName=font_bold, fontSize=8, textColor=colors.white))
        ],
        [
            Paragraph("<b>Faz 4.1</b>", body_style),
            Paragraph("<b>Canlı WebSocket Oran & CLV İzleyici</b>", body_style),
            Paragraph("Açılış oranı ile kapanış oranı (Closing Line Value) arasındaki hareketi izleyerek 'Smart Money' yönünü yakalama.", body_style)
        ],
        [
            Paragraph("<b>Faz 4.2</b>", body_style),
            Paragraph("<b>Tartı & Dehidrasyon Sıkıntı Endeksi (Weight-Cut)</b>", body_style),
            Paragraph("Tartıda zorlanan, titreyen veya kilo düşemeyen dövüşçülerin kardiyo ve çene direncindeki ani %20'lik çöküşü modelleme.", body_style)
        ],
        [
            Paragraph("<b>Faz 4.3</b>", body_style),
            Paragraph("<b>Kamp Kalitesi & Baş Antrenör Matrisi</b>", body_style),
            Paragraph("AKA, City Kickboxing, Trevor Wittman gibi elit kampların maç planı hazırlama üstünlüğünü katsayılaştırma.", body_style)
        ],
        [
            Paragraph("<b>Faz 5.1</b>", body_style),
            Paragraph("<b>100,000 Simülasyonlu Monte Carlo Motoru</b>", body_style),
            Paragraph("Her maç için 100.000 sanal raunt simüle ederek raunt bazlı canlı bahis ve alt/üst arbitrajı üretme.", body_style)
        ],
        [
            Paragraph("<b>Faz 5.2</b>", body_style),
            Paragraph("<b>Otomatik Bahis Yürütme Botu (API Bot)</b>", body_style),
            Paragraph("+EV oranı %5'in üzerindeki fırsatları tespit ettiği milisaniyede kasayı otomatik bölen bahis botu.", body_style)
        ]
    ]

    roadmap_table = Table(roadmap_data, colWidths=[60, 210, 234])
    roadmap_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), C_PRIMARY),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, C_BORDER),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, C_CARD_BG]),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(roadmap_table)
    story.append(Spacer(1, 10))

    # =========================================================================
    # EXECUTIVE SIGN-OFF & ALIGNMENT
    # =========================================================================
    sign_text = (
        "<b>MİMARİ ONAY VE HİZALANMA (LEAD ARCHITECT SIGN-OFF):</b><br/>"
        "UFC Elo ve Değerli Bahis Bulucu sistemimiz, veri temizliğinden matematiksel modellemeye kadar sağlam temellere oturtulmuştur. "
        "Bu Master Plan çerçevesinde disiplinli bir şekilde ilerleyerek, küresel bahis piyasalarında kalıcı ve ölçülebilir bir pozitif getiri (Alpha) elde edeceğiz."
    )
    sign_box = Table([[Paragraph(sign_text, callout_style)]], colWidths=[504])
    sign_box.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f1f5f9')),
        ('BORDER', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
        ('PADDING', (0,0), (-1,-1), 8),
        ('ROUNDEDCORNERS', [4, 4, 4, 4]),
    ]))
    story.append(sign_box)

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"[SUCCESS] PDF generated successfully: {filename}")

if __name__ == '__main__':
    build_pdf("total_master_plan.pdf")
