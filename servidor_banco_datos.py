#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Servidor Backend y Banco de Datos - QuimiQuiz Pro (Tabla Periódica)
Prof. Edwin Ortíz - Química Internacional Pro
Gestiona 3 Bases de Datos Oficiales:
  1. Calificaciones de Alumnos: 'banco_de_datos.csv' y 'banco_de_datos.json'
  2. Suscriptores PRO (1 Mes / 1 Año): 'suscriptores_pro.csv' y 'suscriptores_pro.json'
  3. Listas de Alumnos por Grado/Grupo: 'estudiantes.json'
"""

import os
import sys
import json
import csv
import base64
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler

if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

PORT = 5050
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Archivos de Base de Datos
CSV_FILE = os.path.join(BASE_DIR, "banco_de_datos.csv")
JSON_FILE = os.path.join(BASE_DIR, "banco_de_datos.json")
XLSX_FILE = os.path.join(BASE_DIR, "banco_de_datos.xlsx")
SUBS_CSV_FILE = os.path.join(BASE_DIR, "suscriptores_pro.csv")
SUBS_JSON_FILE = os.path.join(BASE_DIR, "suscriptores_pro.json")
STUDENTS_JSON_FILE = os.path.join(BASE_DIR, "estudiantes.json")

SECRET_SALT = "QUIMICA_PANAMA_PROF_ORTIZ_2026"
SUB_PRIVATE_SALT = "QZ_PRO_V9_EDWIN_ORTIZ_99482716_SEC"

CSV_HEADERS = [
    "Fecha_Hora",
    "Estudiante",
    "Grupo",
    "Aciertos",
    "Total_Items",
    "Nota_Calificacion",
    "Estado",
    "Duracion",
    "Salidas_Pantalla",
    "Codigo_Antifraude",
    "Autenticidad"
]

SUBS_CSV_HEADERS = [
    "Fecha_Activacion",
    "Cliente_Suscriptor",
    "ID_Dispositivo",
    "Plan_Contratado",
    "Monto_USD",
    "Fecha_Vencimiento",
    "Clave_Suscripcion",
    "Estado"
]


def js_imul_32(a, b):
    return ((a & 0xFFFFFFFF) * (b & 0xFFFFFFFF)) & 0xFFFFFFFF


def generate_signature_backend(text_str, salt_str):
    """Misma función criptográfica de 32/53 bits usada por el generador para validar firmas en el Backend."""
    h1 = 0xDEADBEEF
    h2 = 0x41C6CE57
    s = f"{text_str}|{salt_str}"
    for ch in s:
        code = ord(ch)
        h1 = js_imul_32(h1 ^ code, 2654435761)
        h2 = js_imul_32(h2 ^ code, 1597334677)
    h1 = js_imul_32(h1 ^ (h1 >> 16), 2246822507) ^ js_imul_32(h2 ^ (h2 >> 13), 3266489909)
    h2 = js_imul_32(h2 ^ (h2 >> 16), 2246822507) ^ js_imul_32(h1 ^ (h1 >> 13), 3266489909)
    val = 4294967296 * (2097151 & h2) + (h1 & 0xFFFFFFFF)
    return hex(abs(val))[2:].upper().zfill(8)[-8:]


def ensure_databases_initialized():
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, mode="w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(CSV_HEADERS)

    if not os.path.exists(SUBS_CSV_FILE):
        with open(SUBS_CSV_FILE, mode="w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(SUBS_CSV_HEADERS)

    if not os.path.exists(SUBS_JSON_FILE):
        with open(SUBS_JSON_FILE, mode="w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)

    if not os.path.exists(STUDENTS_JSON_FILE):
        with open(STUDENTS_JSON_FILE, mode="w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)


def verify_student_code(code_str, correct):
    if not code_str:
        return "SIN_CODIGO"
    clean = code_str.strip()
    if clean.startswith("#QZ-"):
        clean = clean[4:]
    elif clean.startswith("QZ-"):
        clean = clean[3:]
    elif clean.startswith("#"):
        clean = clean[1:]

    parts = clean.split("-")
    if len(parts) >= 2:
        b64 = "-".join(parts[:-1])
        try:
            padding = (4 - len(b64) % 4) % 4
            b64_padded = (b64 + "=" * padding).replace("-", "+").replace("_", "/")
            decoded = base64.b64decode(b64_padded).decode("utf-8")
            data = json.loads(decoded)
            if int(data.get("c", -1)) == int(correct):
                return "VALIDO"
            return "ALTERADO_O_FALSO"
        except Exception:
            return "ALTERADO_O_FALSO"
    return "VALIDO"


def load_json_file(path):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception:
            pass
    return []



def export_records_to_multisheet_excel(records):
    """Genera banco_de_datos.xlsx dividido en hojas por grupo y consolidado general."""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter

        wb = openpyxl.Workbook()
        wb.remove(wb.active)

        header_fill = PatternFill(start_color="0E7490", end_color="0E7490", fill_type="solid")
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        center_align = Alignment(horizontal="center", vertical="center")
        pass_font = Font(name="Calibri", size=10, bold=True, color="059669")
        fail_font = Font(name="Calibri", size=10, bold=True, color="E11D48")
        bold_font = Font(name="Calibri", size=10, bold=True)

        headers = [
            "N°", "Estudiante (Apellido, Nombre)", "Grado / Grupo", "Aciertos",
            "Total Ítems", "Nota", "Estado", "Salidas Pantalla", "Fecha y Hora", "Código Antifraude"
        ]

        groups_map = {}
        for r in records:
            grp = str(r.get("group", "S/G")).strip() or "Sin Grupo"
            groups_map.setdefault(grp, []).append(r)

        for grp in groups_map:
            groups_map[grp].sort(key=lambda x: str(x.get("name", "")).upper())

        sorted_all = []
        for grp in sorted(groups_map.keys()):
            sorted_all.extend(groups_map[grp])

        def populate_sheet(ws, title_text, data_list):
            ws.append([title_text])
            ws.append([])
            ws.append(headers)

            ws.row_dimensions[1].height = 24
            ws.row_dimensions[3].height = 22
            ws.cell(row=1, column=1).font = Font(name="Calibri", size=14, bold=True, color="0F172A")

            for col_idx in range(1, len(headers) + 1):
                cell = ws.cell(row=3, column=col_idx)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = center_align

            for idx, item in enumerate(data_list, start=1):
                row_num = idx + 3
                status = str(item.get("status", "")).upper()
                row_vals = [
                    idx,
                    str(item.get("name", "")),
                    str(item.get("group", "S/G")),
                    item.get("correct", 0),
                    item.get("total", 50),
                    str(item.get("grade", "--")),
                    status,
                    item.get("switches", 0),
                    str(item.get("datetime", "--")),
                    str(item.get("code", "--"))
                ]
                ws.append(row_vals)
                ws.row_dimensions[row_num].height = 20

                ws.cell(row=row_num, column=1).alignment = center_align
                ws.cell(row=row_num, column=2).font = bold_font
                ws.cell(row=row_num, column=3).alignment = center_align
                ws.cell(row=row_num, column=4).alignment = center_align
                ws.cell(row=row_num, column=5).alignment = center_align
                ws.cell(row=row_num, column=6).alignment = center_align

                status_cell = ws.cell(row=row_num, column=7)
                status_cell.alignment = center_align
                if "APROBADO" in status:
                    status_cell.font = pass_font
                elif "REPROBADO" in status:
                    status_cell.font = fail_font

                ws.cell(row=row_num, column=8).alignment = center_align
                ws.cell(row=row_num, column=9).alignment = center_align
                ws.cell(row=row_num, column=10).alignment = center_align

            for col in ws.columns:
                max_len = max(len(str(cell.value or '')) for cell in col)
                col_letter = get_column_letter(col[0].column)
                ws.column_dimensions[col_letter].width = max(max_len + 3, 11)

        ws_all = wb.create_sheet(title="Consolidado General")
        populate_sheet(ws_all, "REGISTRO GENERAL CONSOLIDADO DE CALIFICACIONES - QUÍMICA", sorted_all)

        for grp in sorted(groups_map.keys()):
            clean_title = re.sub(r'[\\/*?:[\]]', '', grp)[:31] or "Grupo"
            ws_grp = wb.create_sheet(title=clean_title)
            populate_sheet(ws_grp, f"CALIFICACIONES OFICIALES - GRUPO {grp}", groups_map[grp])

        wb.save(XLSX_FILE)
    except Exception as e:
        print(f"Aviso generando XLSX multi-hoja: {e}")


def save_json_file(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class DatabaseRequestHandler(BaseHTTPRequestHandler):
    def _set_cors_headers(self, status=200, content_type="application/json"):
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Type", content_type)
        self.end_headers()

    def do_OPTIONS(self):
        self._set_cors_headers(200)

    def do_GET(self):
        ensure_databases_initialized()
        if self.path == "/api/estado" or self.path == "/":
            self._set_cors_headers(200)
            subs = load_json_file(SUBS_JSON_FILE)
            students = load_json_file(STUDENTS_JSON_FILE)
            status_info = {
                "estado": "ACTIVO",
                "servidor": "Backend QuimiQuiz Pro - Prof. Edwin Ortiz",
                "archivo_calificaciones_csv": CSV_FILE,
                "archivo_suscriptores_csv": SUBS_CSV_FILE,
                "total_suscriptores": len(subs),
                "total_alumnos_registrados": len(students),
                "puerto": PORT
            }
            self.wfile.write(json.dumps(status_info, ensure_ascii=False).encode("utf-8"))

        elif self.path == "/api/calificaciones":
            records = load_json_file(JSON_FILE)
            self._set_cors_headers(200)
            self.wfile.write(json.dumps(records, ensure_ascii=False).encode("utf-8"))

        elif self.path == "/api/suscripciones":
            subs = load_json_file(SUBS_JSON_FILE)
            self._set_cors_headers(200)
            self.wfile.write(json.dumps(subs, ensure_ascii=False).encode("utf-8"))

        elif self.path == "/api/estudiantes":
            students = load_json_file(STUDENTS_JSON_FILE)
            self._set_cors_headers(200)
            self.wfile.write(json.dumps(students, ensure_ascii=False).encode("utf-8"))

        else:
            self._set_cors_headers(404)
            self.wfile.write(b'{"error": "Ruta no encontrada"}')

    def do_POST(self):
        ensure_databases_initialized()
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b"{}"

        try:
            payload = json.loads(post_data.decode("utf-8"))
        except Exception as e:
            self._set_cors_headers(400)
            self.wfile.write(json.dumps({"error": f"JSON invalido: {str(e)}"}).encode("utf-8"))
            return

        # 1. GUARDAR CALIFICACIÓN DE ESTUDIANTE
        if self.path == "/api/guardar":
            name = str(payload.get("name", "ANONIMO")).strip()
            group = str(payload.get("group", "S/G")).strip()
            correct = int(payload.get("correct", 0))
            total = int(payload.get("total", 50))
            date_str = str(payload.get("datetime", datetime.now().strftime("%d/%m/%Y, %H:%M"))).strip()
            grade = str(payload.get("grade", "1.0")).strip()
            status = str(payload.get("status", "REPROBADO")).strip()
            duration = str(payload.get("duration", "0s")).strip()
            switches = int(payload.get("switches", 0))
            code = str(payload.get("code", "")).strip().upper()

            es_autentico = verify_student_code(code, correct)

            row = [date_str, name, group, correct, total, grade, status, duration, switches, code, es_autentico]
            with open(CSV_FILE, mode="a", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f, delimiter=";")
                writer.writerow(row)

            records = load_json_file(JSON_FILE)
            records.append({
                "datetime": date_str,
                "name": name,
                "group": group,
                "correct": correct,
                "total": total,
                "grade": grade,
                "status": status,
                "duration": duration,
                "switches": switches,
                "code": code,
                "authenticity": es_autentico
            })
            save_json_file(JSON_FILE, records)
            export_records_to_multisheet_excel(records)

            print(f"[{datetime.now().strftime('%H:%M:%S')}] [NOTA] {name} ({group}) | Nota: {grade} | {correct}/{total}")
            self._set_cors_headers(200)
            self.wfile.write(json.dumps({"status": "ok", "autenticidad": es_autentico}).encode("utf-8"))

        # 2. REGISTRAR O GENERAR SUSCRIPCIÓN PRO EN BASE DE DATOS
        elif self.path == "/api/suscripciones/registrar":
            client_name = str(payload.get("client", "SUSCRIPTOR PRO")).strip().upper()
            device_id = str(payload.get("deviceId", "----")).strip().upper()
            plan_code = str(payload.get("planCode", "1M")).strip().upper()
            sub_key = str(payload.get("key", "")).strip().upper()
            exp_str = str(payload.get("expDate", "")).strip()
            now_str = datetime.now().strftime("%d/%m/%Y %H:%M")

            plan_label = "Anual (365 dias)" if plan_code == "1A" else "Mensual (30 dias)"
            amount_usd = "9.99" if plan_code == "1A" else "1.00"

            subs = load_json_file(SUBS_JSON_FILE)
            if not any(s.get("key") == sub_key for s in subs):
                new_sub = {
                    "activatedAt": now_str,
                    "client": client_name,
                    "deviceId": device_id,
                    "plan": plan_label,
                    "amountUsd": amount_usd,
                    "expiresAt": exp_str,
                    "key": sub_key,
                    "status": "ACTIVA"
                }
                subs.append(new_sub)
                save_json_file(SUBS_JSON_FILE, subs)

                with open(SUBS_CSV_FILE, mode="a", newline="", encoding="utf-8-sig") as f:
                    writer = csv.writer(f, delimiter=";")
                    writer.writerow([now_str, client_name, device_id, plan_label, amount_usd, exp_str, sub_key, "ACTIVA"])

                print(f"[{datetime.now().strftime('%H:%M:%S')}] [SUSCRIPCION PRO] Cliente: {client_name} | Dispositivo: #{device_id} | Plan: {plan_label} | Clave: {sub_key}")

            self._set_cors_headers(200)
            self.wfile.write(json.dumps({"status": "ok", "total_suscriptores": len(subs)}).encode("utf-8"))

        # 3. GUARDAR LISTA DE ALUMNOS DE UN GRADO / GRUPO
        elif self.path == "/api/estudiantes":
            students_list = payload.get("students", [])
            if isinstance(students_list, list):
                save_json_file(STUDENTS_JSON_FILE, students_list)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [LISTA GRADO] {len(students_list)} alumnos actualizados en estudiantes.json")
                self._set_cors_headers(200)
                self.wfile.write(json.dumps({"status": "ok", "count": len(students_list)}).encode("utf-8"))
            else:
                self._set_cors_headers(400)
                self.wfile.write(b'{"error": "Formato de lista invalido"}')

        else:
            self._set_cors_headers(404)
            self.wfile.write(b'{"error": "Ruta no encontrada"}')


def run():
    ensure_databases_initialized()
    server_address = ("", PORT)
    httpd = HTTPServer(server_address, DatabaseRequestHandler)
    print("=" * 68)
    print("SERVIDOR BACKEND Y BASE DE DATOS - QUIMIQUIZ PRO (PROF. EDWIN ORTIZ)")
    print("=" * 68)
    print(f"API Backend activa en      : http://localhost:{PORT}")
    print(f"BD Calificaciones (Excel)  : {CSV_FILE}")
    print(f"BD Suscriptores PRO (Excel): {SUBS_CSV_FILE}")
    print(f"BD Alumnos por Grado (JSON): {STUDENTS_JSON_FILE}")
    print("=" * 68)
    print("Presiona Ctrl + C en esta ventana para detener el servidor.\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
        httpd.server_close()


if __name__ == "__main__":
    run()
