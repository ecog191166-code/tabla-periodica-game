#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Servidor Local de Banco de Datos - Desafío Tabla Periódica
Prof. Edwin Ortiz - Química Panamá
Recibe calificaciones en vivo y las guarda en 'banco_de_datos.csv'
"""

import os
import sys
import json
import csv
import base64
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

PORT = 5050
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE = os.path.join(BASE_DIR, "banco_de_datos.csv")
JSON_FILE = os.path.join(BASE_DIR, "banco_de_datos.json")
SECRET_SALT = "QUIMICA_PANAMA_PROF_ORTIZ_2026"

CSV_HEADERS = [
    "Fecha_Hora",
    "Estudiante",
    "Grupo",
    "Aciertos",
    "Total_Items",
    "Nota_Panama",
    "Estado",
    "Duracion",
    "Salidas_Pantalla",
    "Codigo_Antifraude",
    "Autenticidad"
]

def ensure_csv_initialized():
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, mode="w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(CSV_HEADERS)

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
        if self.path == "/api/estado" or self.path == "/":
            self._set_cors_headers(200)
            status_info = {
                "estado": "ACTIVO",
                "servidor": "Banco de Datos Quimica Panama",
                "archivo_csv": CSV_FILE,
                "puerto": PORT
            }
            self.wfile.write(json.dumps(status_info, ensure_ascii=False).encode("utf-8"))
        elif self.path == "/api/calificaciones":
            ensure_csv_initialized()
            records = []
            if os.path.exists(JSON_FILE):
                try:
                    with open(JSON_FILE, "r", encoding="utf-8") as f:
                        records = json.load(f)
                except Exception:
                    records = []
            self._set_cors_headers(200)
            self.wfile.write(json.dumps(records, ensure_ascii=False).encode("utf-8"))
        else:
            self._set_cors_headers(404)
            self.wfile.write(b'{"error": "Ruta no encontrada"}')

    def do_POST(self):
        if self.path == "/api/guardar":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)

            try:
                record = json.loads(post_data.decode("utf-8"))
            except Exception as e:
                self._set_cors_headers(400)
                self.wfile.write(json.dumps({"error": f"JSON invalido: {str(e)}"}).encode("utf-8"))
                return

            name = str(record.get("name", "ANONIMO")).strip()
            group = str(record.get("group", "S/G")).strip()
            correct = int(record.get("correct", 0))
            total = int(record.get("total", 50))
            date_str = str(record.get("datetime", datetime.now().strftime("%d/%m/%Y, %H:%M"))).strip()
            grade = str(record.get("grade", "1.0")).strip()
            status = str(record.get("status", "REPROBADO")).strip()
            duration = str(record.get("duration", "0s")).strip()
            switches = int(record.get("switches", 0))
            code = str(record.get("code", "")).strip().upper()

            es_autentico = verify_student_code(code, correct)

            ensure_csv_initialized()
            row = [
                date_str,
                name,
                group,
                correct,
                total,
                grade,
                status,
                duration,
                switches,
                code,
                es_autentico
            ]

            # Guardar en CSV para Excel
            with open(CSV_FILE, mode="a", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f, delimiter=";")
                writer.writerow(row)

            # Guardar también en JSON
            records = []
            if os.path.exists(JSON_FILE):
                try:
                    with open(JSON_FILE, "r", encoding="utf-8") as jf:
                        records = json.load(jf)
                except Exception:
                    records = []

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

            with open(JSON_FILE, "w", encoding="utf-8") as jf:
                json.dump(records, jf, ensure_ascii=False, indent=2)

            print(f"[{datetime.now().strftime('%H:%M:%S')}] Registrado: {name} ({group}) | Nota: {grade} | Aciertos: {correct}/50 | {es_autentico}")

            self._set_cors_headers(200)
            response = {
                "status": "ok",
                "mensaje": "Calificacion guardada con exito en banco_de_datos.csv",
                "autenticidad": es_autentico,
                "archivo": CSV_FILE
            }
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode("utf-8"))
        else:
            self._set_cors_headers(404)
            self.wfile.write(b'{"error": "Ruta no encontrada"}')

def run():
    ensure_csv_initialized()
    server_address = ("", PORT)
    httpd = HTTPServer(server_address, DatabaseRequestHandler)
    print("=" * 60)
    print("SERVIDOR DE BANCO DE DATOS - QUIMICA PROF. EDWIN ORTIZ")
    print("=" * 60)
    print(f"Escuchando en: http://localhost:{PORT}")
    print(f"Archivo de calificaciones: {CSV_FILE}")
    print("Listo para recibir notas y abrir directamente en Excel")
    print("=" * 60)
    print("Presiona Ctrl + C en esta ventana para detener el servidor.\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
        httpd.server_close()

if __name__ == "__main__":
    run()
