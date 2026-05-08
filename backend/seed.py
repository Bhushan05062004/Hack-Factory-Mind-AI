"""
Factory Mind AI — Demo Data Seeder
Inserts 3 users, 10 products, 5 SOPs and builds FAISS indices.

Usage:
    python seed.py              # Seed all demo data
    python seed.py --rebuild    # Only rebuild FAISS indices
"""

import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

import google.generativeai as genai
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

from db import init_db, get_connection
from auth import create_access_token



# ─────────────────────────────────────────────
#  DEMO USERS (3 roles) + Admin
# ─────────────────────────────────────────────
DEMO_USERS = [
    {"email": "alice@demo.com", "name": "Alice Johnson", "role": "user", "password": "123"},
    {"email": "bob@demo.com", "name": "Bob Martinez", "role": "operator", "password": "123"},
    {"email": "carol@demo.com", "name": "Carol Chen", "role": "quality", "password": "123"},
    {"email": "admin", "name": "Admin", "role": "operator", "password": "123"},
]


# ─────────────────────────────────────────────
#  DEMO PRODUCTS (10 precision-manufacturing items)
# ─────────────────────────────────────────────
DEMO_PRODUCTS = [
    {
        "part_number": "TF-80-A",
        "name": "Titanium Flange",
        "material": "Titanium Grade 5",
        "specification": "Aerospace grade, 80 mm bore, ASTM B381",
        "description": "High-strength titanium flange for aerospace applications. 80 mm bore diameter with precision-machined sealing surfaces.",
    },
    {
        "part_number": "SB-M10-SS",
        "name": "Steel Bracket",
        "material": "Stainless Steel 316L",
        "specification": "M10 mounting, load capacity 500 kg",
        "description": "Heavy-duty stainless steel mounting bracket. Corrosion-resistant 316L grade for marine and chemical environments.",
    },
    {
        "part_number": "CP-25-C1",
        "name": "Copper Pipe",
        "material": "Copper C101",
        "specification": "25 mm OD, 1.5 mm wall, ASTM B88",
        "description": "High-purity copper pipe for plumbing and HVAC. Type L hard-drawn with 25 mm outer diameter.",
    },
    {
        "part_number": "AG-50-7075",
        "name": "Aluminum Gear",
        "material": "Aluminum 7075-T6",
        "specification": "50-tooth spur gear, module 2, bore 20 mm",
        "description": "Precision CNC-machined aluminum spur gear. Aircraft-grade 7075-T6 alloy for lightweight high-strength applications.",
    },
    {
        "part_number": "RG-30-NBR",
        "name": "Rubber Gasket",
        "material": "Nitrile Rubber (NBR)",
        "specification": "30 mm ID, 50 mm OD, 3 mm thick, Shore A 70",
        "description": "Oil-resistant nitrile rubber gasket for sealing flanged connections. Temperature range -40 to 120 degrees C.",
    },
    {
        "part_number": "TB-M8-GR8",
        "name": "Titanium Bolt",
        "material": "Titanium Grade 8",
        "specification": "M8x50, hex head, Grade 8 strength",
        "description": "High-tensile titanium bolt for critical aerospace fastening. M8 thread, 50 mm length, hex head.",
    },
    {
        "part_number": "AR-100-6061",
        "name": "Aluminum Rod",
        "material": "Aluminum 6061-T6",
        "specification": "100 mm diameter, 1 m length, anodized",
        "description": "Extruded aluminum rod stock for machining. 6061-T6 alloy, 100 mm diameter, available in 1 m lengths.",
    },
    {
        "part_number": "SV-DN50-316",
        "name": "Stainless Steel Valve",
        "material": "Stainless Steel 316",
        "specification": "DN50, ball valve, 1000 PSI, tri-clamp",
        "description": "Sanitary ball valve for pharmaceutical and food processing. DN50 tri-clamp connection, 316 stainless steel body.",
    },
    {
        "part_number": "CB-12-1045",
        "name": "Carbon Steel Bearing",
        "material": "Carbon Steel 1045",
        "specification": "12 mm bore, 32 mm OD, sealed, 6201",
        "description": "Deep-groove ball bearing with sealed design. 12 mm bore, 32 mm outer diameter, 10 mm width. For general industrial use.",
    },
    {
        "part_number": "IH-200-A36",
        "name": "I-Beam (Steel)",
        "material": "Structural Steel A36",
        "specification": "W200x46, 6 m length, hot-rolled",
        "description": "Standard structural I-beam for construction. W200x46 profile, ASTM A36 steel, 6 meter length.",
    },
]


# ─────────────────────────────────────────────
#  DEMO SOPs (5 standard operating procedures)
# ─────────────────────────────────────────────
DEMO_SOPS = [
    {
        "title": "Flange Inspection Procedure",
        "category": "inspection",
        "content": (
            "1. Visual Inspection: Check for surface defects, cracks, or corrosion on sealing faces. "
            "2. Dimensional Check: Verify bore diameter (±0.05 mm), OD, and bolt-hole spacing with calibrated calipers. "
            "3. Surface Finish: Measure Ra value on sealing face — must be ≤ 3.2 µm. "
            "4. Material Cert: Cross-reference heat number with mill certificate. "
            "5. Pressure Test: Hydrostatic test at 1.5x rated pressure for 10 minutes — no leaks allowed. "
            "6. Documentation: Record all measurements on QC Form FI-001, sign and date."
        ),
    },
    {
        "title": "Weld Quality Assessment",
        "category": "welding",
        "content": (
            "1. Pre-Weld: Verify welder certification (AWS D1.1), check WPS compliance, confirm preheat temperature. "
            "2. Visual: Inspect for undercut (max 0.8 mm), porosity, incomplete fusion, and spatter. "
            "3. NDT: Perform radiographic testing (RT) on all critical welds per ASME Section V. "
            "4. Mechanical: Conduct bend tests and tensile tests per WPS requirements. "
            "5. Documentation: Complete weld map, log all NDT results in quality database."
        ),
    },
    {
        "title": "Surface Treatment Protocol",
        "category": "finishing",
        "content": (
            "1. Cleaning: Degrease parts with alkaline wash at 60°C for 15 minutes. "
            "2. Etching: Acid etch (HF/HNO3 solution) for titanium; phosphoric acid for steel. "
            "3. Coating: Apply primer within 4 hours of etching. Measure dry film thickness (DFT) — min 25 µm. "
            "4. Curing: Oven cure at 180°C for 30 minutes. Verify with thermocouple. "
            "5. Adhesion Test: Cross-cut tape test per ASTM D3359 — must achieve 4B rating or higher."
        ),
    },
    {
        "title": "Dimensional Verification Checklist",
        "category": "measurement",
        "content": (
            "1. Equipment: Use calibrated CMM (coordinate measuring machine) or precision micrometers/calipers. "
            "2. Datum Setup: Establish primary datum per engineering drawing. "
            "3. Critical Dimensions: Measure all GD&T callouts — true position, concentricity, runout. "
            "4. Tolerances: General ±0.1 mm; precision features ±0.02 mm unless drawing specifies otherwise. "
            "5. Report: Generate CMM report with actual vs. nominal values. Flag any out-of-tolerance conditions."
        ),
    },
    {
        "title": "Material Certification Review",
        "category": "materials",
        "content": (
            "1. Receipt: Log incoming material with PO number, heat/lot number, supplier name. "
            "2. Certificate Check: Verify mill test report (MTR) includes chemical composition and mechanical properties. "
            "3. Compliance: Confirm material meets specification (e.g., ASTM, AMS, EN standard) per purchase order. "
            "4. Traceability: Stamp or label material with internal tracking number. Enter into MRP system. "
            "5. Rejection: If MTR does not match PO spec, quarantine material and issue NCR (Non-Conformance Report)."
        ),
    },
]


def seed_data() -> None:
    """Insert all demo data into the database."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS users")
    conn.commit()
    conn.close()

    init_db()
    from db import hash_password
    
    conn = get_connection()
    cur = conn.cursor()

    # Seed users
    for u in DEMO_USERS:
        hashed = hash_password(u["password"])
        cur.execute(
            "INSERT OR IGNORE INTO users (email, name, password, role) VALUES (?, ?, ?, ?)",
            (u["email"], u["name"], hashed, u["role"]),
        )


    # Seed products
    for p in DEMO_PRODUCTS:
        cur.execute(
            "INSERT OR IGNORE INTO products (part_number, name, material, specification, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (p["part_number"], p["name"], p["material"], p["specification"], p["description"]),
        )

    # Seed SOPs
    for s in DEMO_SOPS:
        cur.execute(
            "INSERT OR IGNORE INTO sops (title, content, category) VALUES (?, ?, ?)",
            (s["title"], s["content"], s["category"]),
        )

    conn.commit()
    conn.close()
    print("✅ Demo data seeded: 3 users, 10 products, 5 SOPs")


def build_indices() -> None:
    """Build FAISS indices for products and SOPs."""
    from products import build_product_index
    from sops import build_sop_index

    n_products = build_product_index()
    print(f"✅ Product FAISS index built: {n_products} products indexed")

    n_sops = build_sop_index()
    print(f"✅ SOP FAISS index built: {n_sops} SOPs indexed")


def print_jwts() -> None:
    """Print demo JWTs for all three roles."""
    conn = get_connection()
    rows = conn.execute("SELECT id, email, name, role FROM users").fetchall()
    conn.close()

    print("\n" + "=" * 60)
    print("  DEMO JWT TOKENS")
    print("=" * 60)
    for row in rows:
        token = create_access_token(row["id"], row["role"], row["name"])
        print(f"\n  {row['role'].upper()} — {row['name']} ({row['email']})")
        print(f"  Token: {token}")
    print("\n" + "=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Factory Mind AI Demo Seeder")
    parser.add_argument("--rebuild", action="store_true", help="Only rebuild FAISS indices")
    args = parser.parse_args()

    if args.rebuild:
        build_indices()
    else:
        seed_data()
        build_indices()
        print_jwts()
