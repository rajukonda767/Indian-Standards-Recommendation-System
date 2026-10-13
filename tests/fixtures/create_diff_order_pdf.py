# -*- coding: utf-8 -*-
"""
tests/fixtures/create_diff_order_pdf.py
Creates a realistic PDF with a different column order:
[Quantity | Unit | Material Code | Short Description | Technical Specification | Sl.No]
to test dynamic header mapping on the block-based path.
"""
import os
import pymupdf

out_dir = r"C:\Users\devag\.gemini\antigravity\scratch\standards\tests\fixtures"
os.makedirs(out_dir, exist_ok=True)
pdf_path = os.path.join(out_dir, "diff_order_bid.pdf")

doc = pymupdf.open()
p1 = doc.new_page(width=595, height=842)

p1.insert_text((45, 60), "TENDER SPECIFICATION - CABLE PROCUREMENT SCHEDULE", fontsize=12)
p1.insert_text((45, 90), "SCHEDULE OF REQUIREMENTS (REORDERED COLUMNS)", fontsize=10)

# Table Header with Reordered Columns:
# Col 0: Quantity, Col 1: Unit, Col 2: Material Code, Col 3: Short Description, Col 4: Technical Specification, Col 5: Sl.No
p1.insert_text((45, 130), "Quantity | Unit | Material Code | Short Description | Technical Specification | Sl.No", fontsize=9)

# Data Rows
p1.insert_text((45, 170), "3000 | MTR | CBLE-1001 | FRLS Low Smoke Cable 1C x 2.5 | Conforming to IS 694 Class 5 | 1", fontsize=9)
p1.insert_text((45, 210), "5000 | MTR | CBLE-1002 | XLPE Armoured Cable 3C x 4.0 | Conforming to IS 7098 Part 1 | 2", fontsize=9)
p1.insert_text((45, 250), "1500 | MTR | CBLE-1003 | PVC Control Cable 10CX1.5 | Conforming to IS 1554 Part 1 | 3", fontsize=9)

p1.insert_text((550, 810), "1 / 1", fontsize=8)

doc.save(pdf_path)
print(f"Created reordered column PDF fixture at: {pdf_path}")
