#!/usr/bin/env python3
"""
Script de Migração e Refatoração Estrutural do Banco de Dados RPA Vagas.
Garante compatibilidade retroativa e migração das 486 candidaturas existentes.
"""
import sqlite3
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("db_migration")

DB_PATH = Path("/home/candidato/DEV/RPA-VAGAS/data/rpa_vagas.db")

def migrate():
    if not DB_PATH.exists():
        logger.error(f"Banco não encontrado em {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    logger.info("Iniciando transação de migração...")
    cursor.execute("BEGIN TRANSACTION;")

    try:
        # 1. Tabela candidaturas (refatorada)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS candidaturas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id TEXT UNIQUE NOT NULL,
            job_name TEXT NOT NULL,
            company TEXT NOT NULL,
            subdomain TEXT,
            direct_url TEXT NOT NULL,
            workplace_type TEXT,
            job_status TEXT,
            application_status TEXT,
            current_step INTEGER DEFAULT 0,
            total_steps INTEGER DEFAULT 0,
            status_esteira TEXT DEFAULT 'PENDENTE_VARREDURA',
            ultima_etapa_nome TEXT,
            ultima_verificacao TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # 2. Tabela etapas_vagas
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS etapas_vagas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id TEXT NOT NULL,
            ordem INTEGER DEFAULT 0,
            nome_etapa TEXT NOT NULL,
            tipo_etapa TEXT DEFAULT 'DESCONHECIDO',
            status_etapa TEXT DEFAULT 'PENDENTE',
            detalhes_json TEXT,
            data_identificacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            data_conclusao TIMESTAMP,
            FOREIGN KEY (application_id) REFERENCES candidaturas (application_id) ON DELETE CASCADE
        );
        """)

        # 3. Tabela questionarios_respostas_cache
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS questionarios_respostas_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hash_pergunta TEXT UNIQUE NOT NULL,
            texto_pergunta TEXT NOT NULL,
            tipo_campo TEXT NOT NULL,
            opcoes_disponiveis TEXT,
            resposta_escolhida TEXT NOT NULL,
            justificativa_ia TEXT,
            modelo_ia TEXT NOT NULL,
            data_resposta TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # 4. Tabela log_execucoes_rpa
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS log_execucoes_rpa (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id TEXT NOT NULL,
            etapa_nome TEXT,
            acao TEXT NOT NULL,
            sucesso INTEGER NOT NULL DEFAULT 1,
            mensagem TEXT,
            screenshot_path TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # Migrar dados legados de candidaturas_acompanhamento se existir
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='candidaturas_acompanhamento';")
        if cursor.fetchone():
            logger.info("Migrando dados de candidaturas_acompanhamento para candidaturas...")
            cursor.execute("""
            INSERT OR IGNORE INTO candidaturas (
                application_id, job_name, company, subdomain, direct_url,
                workplace_type, job_status, application_status, current_step,
                total_steps, status_esteira, updated_at
            )
            SELECT 
                application_id, job_name, company, subdomain, direct_url,
                workplace_type, job_status, application_status, current_step,
                total_steps, 'PENDENTE_VARREDURA', updated_at
            FROM candidaturas_acompanhamento;
            """)
            migrados = cursor.rowcount
            logger.info(f"Registros migrados com sucesso: {migrados}")

        conn.commit()
        logger.info("Migração concluída com sucesso.")
        return True

    except Exception as e:
        conn.rollback()
        logger.error(f"Erro durante a migração: {e}")
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    success = migrate()
    exit(0 if success else 1)
