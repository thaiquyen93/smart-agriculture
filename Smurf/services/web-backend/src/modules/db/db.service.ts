import { Injectable, Logger, OnModuleInit } from '@nestjs/common';
import * as path from 'path';
import * as fs from 'fs';

// eslint-disable-next-line @typescript-eslint/no-var-requires
const BetterSqlite3 = require('better-sqlite3');

@Injectable()
export class DbService implements OnModuleInit {
  private readonly logger = new Logger(DbService.name);
  private db: any;

  onModuleInit() {
    this.initDb();
  }

  private initDb() {
    const dbPath =
      process.env.DB_FILE ||
      path.resolve(__dirname, '../../../../../database-saver/data/smurf_database.sqlite');

    try {
      const dir = path.dirname(dbPath);
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }

      this.db = new BetterSqlite3(dbPath, {
        verbose: process.env.NODE_ENV === 'development' ? console.log : undefined,
      });
      this.db.pragma('journal_mode = WAL');
      this.logger.log(`✓ SQLite Database connected at: ${dbPath}`);
    } catch (err) {
      this.logger.error(`Failed to initialize SQLite Database: ${err.message}`, err.stack);
    }
  }

  // =========================================================================
  // IRRIGATION PLANS (Track B Plan Verification Loop)
  // =========================================================================

  getPlans(status?: string, limit: number = 50): any[] {
    try {
      if (status) {
        const stmt = this.db.prepare(
          'SELECT * FROM irrigation_plans WHERE status = ? ORDER BY id DESC LIMIT ?',
        );
        return stmt.all(status, limit) as any[];
      } else {
        const stmt = this.db.prepare(
          'SELECT * FROM irrigation_plans ORDER BY id DESC LIMIT ?',
        );
        return stmt.all(limit) as any[];
      }
    } catch (err) {
      this.logger.warn(`Error querying irrigation_plans: ${err.message}`);
      return [];
    }
  }

  getPlanById(planId: string): any {
    try {
      const stmt = this.db.prepare(
        'SELECT * FROM irrigation_plans WHERE plan_id = ? LIMIT 1',
      );
      return stmt.get(planId) || null;
    } catch (err) {
      this.logger.warn(`Error querying plan by id ${planId}: ${err.message}`);
      return null;
    }
  }

  updatePlanStatus(planId: string, status: string): any {
    try {
      const stmt = this.db.prepare(
        'UPDATE irrigation_plans SET status = ? WHERE plan_id = ?',
      );
      const res = stmt.run(status, planId);
      this.logger.log(`💾 [DB UPDATE] Plan ${planId} -> ${status} (Changes: ${res.changes})`);
      return { success: res.changes > 0, plan_id: planId, status };
    } catch (err) {
      this.logger.error(`Error updating plan status: ${err.message}`);
      throw err;
    }
  }

  // =========================================================================
  // INSPECTION TASKS (Track B Field Maintenance Loop)
  // =========================================================================

  getTasks(status?: string, limit: number = 50): any[] {
    try {
      if (status) {
        const stmt = this.db.prepare(
          'SELECT * FROM inspection_tasks WHERE status = ? ORDER BY id DESC LIMIT ?',
        );
        return stmt.all(status, limit) as any[];
      } else {
        const stmt = this.db.prepare(
          'SELECT * FROM inspection_tasks ORDER BY id DESC LIMIT ?',
        );
        return stmt.all(limit) as any[];
      }
    } catch (err) {
      this.logger.warn(`Error querying inspection_tasks: ${err.message}`);
      return [];
    }
  }

  getTaskById(taskId: string): any {
    try {
      const stmt = this.db.prepare(
        'SELECT * FROM inspection_tasks WHERE task_id = ? LIMIT 1',
      );
      return stmt.get(taskId) || null;
    } catch (err) {
      this.logger.warn(`Error querying task by id ${taskId}: ${err.message}`);
      return null;
    }
  }

  updateTaskStatus(taskId: string, status: string = 'CLOSED', verificationStatus: string = 'VERIFIED'): any {
    try {
      const stmt = this.db.prepare(
        'UPDATE inspection_tasks SET status = ?, verification_status = ? WHERE task_id = ?',
      );
      const res = stmt.run(status, verificationStatus, taskId);
      this.logger.log(`💾 [DB UPDATE] Task ${taskId} -> ${status} (${verificationStatus})`);
      return { success: res.changes > 0, task_id: taskId, status, verification_status: verificationStatus };
    } catch (err) {
      this.logger.error(`Error updating task status: ${err.message}`);
      throw err;
    }
  }

  // =========================================================================
  // MULTI-AGENT LOGS & EVIDENCE (Reasoning Trace)
  // =========================================================================

  getAgentLogs(sessionId?: string, agentName?: string, limit: number = 50) {
    try {
      let query = 'SELECT * FROM agent_logs WHERE 1=1';
      const params: any[] = [];

      if (sessionId) {
        query += ' AND session_id = ?';
        params.push(sessionId);
      }
      if (agentName) {
        query += ' AND agent_name = ?';
        params.push(agentName);
      }

      query += ' ORDER BY id DESC LIMIT ?';
      params.push(limit);

      const stmt = this.db.prepare(query);
      const rows: any[] = stmt.all(...params);

      return rows.map((r) => {
        let evidence = null;
        if (r.evidence_data) {
          try {
            evidence = JSON.parse(r.evidence_data);
          } catch {
            evidence = r.evidence_data;
          }
        }
        return {
          ...r,
          evidence_data: evidence,
        };
      });
    } catch (err) {
      this.logger.warn(`Error querying agent_logs: ${err.message}`);
      return [];
    }
  }

  // =========================================================================
  // TELEMETRY & 6 DEVICES STATE QUERY
  // =========================================================================

  getLatestDeviceStates(): Record<string, any> {
    const devices = ['SOIL_01', 'WEATHER_01', 'PUMP_01', 'PH_01', 'TANK_01', 'SUN_01'];
    const result: Record<string, any> = {};

    try {
      const stmt = this.db.prepare(
        'SELECT * FROM telemetry_raw WHERE device_id = ? ORDER BY id DESC LIMIT 1',
      );

      for (const dev of devices) {
        const row: any = stmt.get(dev);
        if (row) {
          try {
            const payload = JSON.parse(row.payload);
            result[dev] = {
              ...payload,
              db_id: row.id,
              db_created_at: row.created_at,
              topic_name: row.topic_name,
            };
          } catch {
            result[dev] = row;
          }
        }
      }
    } catch (err) {
      this.logger.warn(`Error getting latest device states: ${err.message}`);
    }

    return result;
  }

  getDeviceHistory(deviceId: string, limit: number = 25): any[] {
    try {
      const stmt = this.db.prepare(
        'SELECT * FROM telemetry_raw WHERE device_id = ? ORDER BY id DESC LIMIT ?',
      );
      const rows = stmt.all(deviceId, limit);
      
      const history = [];
      for (const row of rows) {
        try {
          const payload = JSON.parse(row.payload);
          history.push({
            ...payload,
            db_id: row.id,
            event_time: row.created_at,
            topic_name: row.topic_name
          });
        } catch {
          history.push(row);
        }
      }
      
      // Reverse to return in chronological order (oldest first, newest last)
      return history.reverse();
    } catch (err) {
      this.logger.warn(`Error getting device history for ${deviceId}: ${err.message}`);
      return [];
    }
  }
}
