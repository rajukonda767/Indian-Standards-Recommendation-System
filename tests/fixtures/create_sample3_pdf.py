# -*- coding: utf-8 -*-
"""
tests/fixtures/create_sample3_pdf.py
Creates a realistic 3-page synthetic GeM bid PDF to test adapter generalization.
"""
import os
import pymupdf

out_dir = r"C:\Users\devag\.gemini\antigravity\scratch\standards\tests\fixtures"
os.makedirs(out_dir, exist_ok=True)
pdf_path = os.path.join(out_dir, "gem_bid_sample3.pdf")

doc = pymupdf.open()

# Page 1: Bid Details & Two-Column GeMARPTS Metadata
p1 = doc.new_page(width=595, height=842)
p1.insert_text((45, 60), "बिड विवरण / Bid Details - Bid Number: GEM/2026/B/9999999", fontsize=12)
p1.insert_text((45, 120), "कुल मात्रा / Total Quantity: 500 Meters", fontsize=10)

# Two-column key-value rows
# Row 1: Searched Result (CONTEXT_ONLY)
p1.insert_text((45, 200), "GeMARPTS में खोजा गया परिणाम / Searched Result generated in GeMARPTS", fontsize=9)
p1.insert_text((276, 200), "Mild Steel Tubes conforming to IS 1239 (Part 1) and Steel Plates to IS 2062", fontsize=9)

# Row 2: Relevant Categories (CORROBORATING)
p1.insert_text((45, 260), "अधिसूचना के लिए चयनित प्रासंगिक श्रेणियाँ / Relevant Categories selected for notification", fontsize=9)
p1.insert_text((276, 260), "Steel Pipes for Water and Sewage conforming to IS 3589", fontsize=9)

p1.insert_text((45, 320), "Buyer Details: Ministry of Jal Shakti, Department of Water Resources", fontsize=10)
p1.insert_text((550, 810), "1 / 3", fontsize=8)

# Page 2: Technical Specifications & Buyer ATC (AUTHORITATIVE)
p2 = doc.new_page(width=595, height=842)
p2.insert_text((45, 60), "तकनीकी विशिष्टियाँ / Technical Specifications", fontsize=12)
p2.insert_text((45, 100), "Specification: RCC structures must be designed in accordance with IS 456:2000 code of practice.", fontsize=10)
p2.insert_text((45, 200), "Buyer Added Bid Specific Terms and Conditions", fontsize=11)
p2.insert_text((45, 230), "Clause 1: Structural steel sections shall strictly comply with IS 808:2021 dimensions.", fontsize=10)
p2.insert_text((550, 810), "2 / 3", fontsize=8)

# Page 3: General Terms and Conditions (GTC - CONTEXT_ONLY)
p3 = doc.new_page(width=595, height=842)
p3.insert_text((45, 60), "This Bid is governed by the General Terms and Conditions, conditions stipulated in GeM Marketplace.", fontsize=10)
p3.insert_text((45, 100), "Standard pipe fittings referenced in generic GTC clause 12 shall conform to IS 1239 (Part 2).", fontsize=10)
p3.insert_text((230, 400), "---धन्यवाद/Thank You---", fontsize=12)
p3.insert_text((550, 810), "3 / 3", fontsize=8)

doc.save(pdf_path)
print(f"Created third GeM bid fixture at: {pdf_path}")
