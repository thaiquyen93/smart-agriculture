import { Injectable, OnModuleInit, OnModuleDestroy, Logger } from '@nestjs/common';
import { Kafka, Consumer, Producer, EachMessagePayload } from 'kafkajs';
import { EventsGateway } from '../websocket/events.gateway';

@Injectable()
export class KafkaService implements OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger(KafkaService.name);
  private kafka: Kafka;
  private consumer: Consumer;
  private producer: Producer;

  private latestTelemetry = new Map<string, any>();
  private latestForecasts = new Map<string, any>();
  private slidingWindows = new Map<string, any>();
  private hourlyWindows = new Map<string, any>();
  private alerts: any[] = [];
  private irrigationPlans: any[] = [];
  private inspectionTasks: any[] = [];
  private agentLogs: any[] = [];

  private topicRaw: string;
  private topicP: string;
  private topicH: string;
  private topicAlerts: string;
  private topicForecasts: string;
  private topicPlans: string;
  private topicTasks: string;
  private topicAgentLogs: string;
  private topicRequests: string;

  constructor(private readonly eventsGateway: EventsGateway) {
    const brokers = (process.env.KAFKA_BOOTSTRAP_SERVERS || 'localhost:9092').split(',');
    this.kafka = new Kafka({
      clientId: 'smurf-web-backend',
      brokers,
    });

    this.consumer = this.kafka.consumer({
      groupId: `smurf-backend-group-${Date.now()}`,
    });
    this.producer = this.kafka.producer();

    this.topicRaw = process.env.TOPIC_RAW || 'topic_raw';
    this.topicP = process.env.TOPIC_P || 'topic_p';
    this.topicH = process.env.TOPIC_H || 'topic_h';
    this.topicAlerts = process.env.TOPIC_ALERTS || 'topic_alerts';
    this.topicForecasts = process.env.TOPIC_FORECASTS || 'topic_forecasts';
    this.topicPlans = process.env.TOPIC_IRRIGATION_PLANS || 'topic_irrigation_plans';
    this.topicTasks = process.env.TOPIC_INSPECTION_TASKS || 'topic_inspection_tasks';
    this.topicAgentLogs = process.env.TOPIC_AGENT_LOGS || 'topic_agent_logs';
    this.topicRequests = process.env.TOPIC_REQUESTS || 'topic_requests';
  }

  async onModuleInit() {
    try {
      await this.producer.connect();
      this.logger.log('✓ Kafka Producer connected');

      await this.consumer.connect();
      this.logger.log('✓ Kafka Consumer connected to Redpanda Kafka');

      const topics = [
        this.topicRaw,
        this.topicP,
        this.topicH,
        this.topicAlerts,
        this.topicForecasts,
        this.topicPlans,
        this.topicTasks,
        this.topicAgentLogs,
      ];

      await this.consumer.subscribe({
        topics,
        fromBeginning: false,
      });

      this.logger.log(`📌 Subscribed to Kafka Topics: ${topics.join(', ')}`);

      await this.consumer.run({
        eachMessage: async ({ topic, message }: EachMessagePayload) => {
          if (!message.value) return;
          try {
            const payload = JSON.parse(message.value.toString());
            const devId = payload.device_id || payload.device_code || payload.station_id || 'UNKNOWN';

            if (topic === this.topicRaw) {
              payload.device_id = devId;
              this.latestTelemetry.set(devId, payload);
              this.eventsGateway.broadcast('TELEMETRY_RAW', payload);
            } else if (topic === this.topicP) {
              this.slidingWindows.set(devId, payload);
              this.eventsGateway.broadcast('WINDOW_MINUTE', payload);
            } else if (topic === this.topicH) {
              this.hourlyWindows.set(devId, payload);
              this.eventsGateway.broadcast('WINDOW_HOURLY', payload);
            } else if (topic === this.topicAlerts) {
              this.alerts.unshift({ ...payload, ack: false });
              if (this.alerts.length > 50) this.alerts.pop();
              this.eventsGateway.broadcast('ALERT_EVENT', payload);
            } else if (topic === this.topicForecasts) {
              this.latestForecasts.set(devId, payload);
              this.eventsGateway.broadcast('AI_FORECAST', payload);
            } else if (topic === this.topicPlans) {
              const planId = payload.plan_id || `PLAN-${Date.now()}`;
              const existingIdx = this.irrigationPlans.findIndex(p => p.plan_id === planId);
              if (existingIdx >= 0) {
                this.irrigationPlans[existingIdx] = payload;
              } else {
                this.irrigationPlans.unshift(payload);
              }
              this.eventsGateway.broadcast('IRRIGATION_PLAN', payload);
            } else if (topic === this.topicTasks) {
              const taskId = payload.task_id || `TASK-${Date.now()}`;
              const existingIdx = this.inspectionTasks.findIndex(t => t.task_id === taskId);
              if (existingIdx >= 0) {
                this.inspectionTasks[existingIdx] = payload;
              } else {
                this.inspectionTasks.unshift(payload);
              }
              this.eventsGateway.broadcast('INSPECTION_TASK', payload);
            } else if (topic === this.topicAgentLogs) {
              this.agentLogs.unshift(payload);
              if (this.agentLogs.length > 100) this.agentLogs.pop();
              this.eventsGateway.broadcast('AGENT_LOG', payload);
            }
          } catch (err: any) {
            this.logger.error(`Error parsing message on topic ${topic}: ${err?.message}`);
          }
        },
      });
    } catch (e: any) {
      this.logger.error(`Failed to initialize Kafka: ${e?.message}`);
    }
  }

  async onModuleDestroy() {
    try {
      await this.consumer.disconnect();
      await this.producer.disconnect();
    } catch (e: any) {
      this.logger.warn(`Error disconnecting Kafka: ${e?.message}`);
    }
  }

  // --- API DATA GETTERS & HANDLERS ---

  getLatestTelemetry() {
    return Array.from(this.latestTelemetry.values());
  }

  getLatestForecasts() {
    return Array.from(this.latestForecasts.values());
  }

  getSlidingWindows() {
    return Array.from(this.slidingWindows.values());
  }

  getHourlyWindows() {
    return Array.from(this.hourlyWindows.values());
  }

  getAlerts() {
    return this.alerts;
  }

  ackAlert(alertId: string) {
    const alert = this.alerts.find(a => a.alert_id === alertId);
    if (alert) {
      alert.ack = true;
      alert.ack_at = Date.now();
    }
    return alert || { status: 'NOT_FOUND' };
  }

  getIrrigationPlans() {
    return this.irrigationPlans;
  }

  approvePlan(planId: string, managerNote?: string) {
    const plan = this.irrigationPlans.find(p => p.plan_id === planId);
    if (plan) {
      plan.status = 'APPROVED';
      plan.approved_at = Date.now();
      plan.manager_note = managerNote || 'Approved via Control Room Dashboard';
      this.eventsGateway.broadcast('IRRIGATION_PLAN_UPDATED', plan);
    }
    return plan || { status: 'NOT_FOUND' };
  }

  rejectPlan(planId: string, reason?: string) {
    const plan = this.irrigationPlans.find(p => p.plan_id === planId);
    if (plan) {
      plan.status = 'REJECTED';
      plan.rejected_at = Date.now();
      plan.reject_reason = reason || 'Rejected by Farm Manager';
      this.eventsGateway.broadcast('IRRIGATION_PLAN_UPDATED', plan);
    }
    return plan || { status: 'NOT_FOUND' };
  }

  getInspectionTasks() {
    return this.inspectionTasks;
  }

  createInspectionTask(taskData: any) {
    const newTask = {
      task_id: `TASK-${Date.now()}`,
      device_id: taskData.device_id || 'PUMP_01',
      description: taskData.description || 'Routine Field Check',
      assigned_to: taskData.assigned_to || 'Field Operator',
      status: 'OPEN',
      created_at: Date.now(),
    };
    this.inspectionTasks.unshift(newTask);
    this.eventsGateway.broadcast('INSPECTION_TASK', newTask);
    return newTask;
  }

  verifyTask(taskId: string, verifierNote?: string) {
    const task = this.inspectionTasks.find(t => t.task_id === taskId);
    if (task) {
      task.status = 'VERIFIED';
      task.verified_at = Date.now();
      task.verifier_note = verifierNote || 'Verified on site';
      this.eventsGateway.broadcast('INSPECTION_TASK_UPDATED', task);
    }
    return task || { status: 'NOT_FOUND' };
  }

  getAgentLogs() {
    return this.agentLogs;
  }

  async handleAIQuery(prompt: string) {
    const telemetry = this.getLatestTelemetry();
    let reply = `[SMURF Multi-Agent Copilot]\n\n`;
    reply += `📊 Trạng thái hiện tại của Nông trường:\n`;

    if (telemetry.length === 0) {
      reply += `- Đang chờ dữ liệu cảm biến từ hệ thống Redpanda Kafka...\n`;
    } else {
      telemetry.forEach(dev => {
        const id = dev.device_id || dev.device_code || 'DEV';
        if (id.includes('SOIL')) {
          reply += `- Cảm biến đất ${id}: Độ ẩm ${dev.soil_moisture ?? '--'}%, Nhiệt độ đất ${dev.temperature ?? '--'}°C\n`;
        } else if (id.includes('WEATHER')) {
          reply += `- Trạm thời tiết ${id}: Nhiệt độ ${dev.temperature ?? '--'}°C, Độ ẩm không khí ${dev.humidity ?? '--'}%\n`;
        } else if (id.includes('TANK')) {
          reply += `- Bồn nước ${id}: Mực nước ${dev.level ?? '--'}%\n`;
        } else if (id.includes('PUMP')) {
          reply += `- Trạm bơm ${id}: Trạng thái ${dev.status ?? 'OFF'}, Lưu lượng ${dev.flow_rate ?? 0} L/m\n`;
        }
      });
    }

    reply += `\n🤖 Khuyên dùng của Multi-Agent System:\n`;
    const soil = telemetry.find(t => (t.device_id || '').includes('SOIL'));
    if (soil && (soil.soil_moisture || 100) < 35) {
      reply += `⚠️ CẢNH BÁO ĐỘ ẨM ĐẤT THẤP (${soil.soil_moisture}% < 35%). Khuyên dùng: Kích hoạt Kế hoạch tưới 450L ngay lập tức!`;
    } else {
      reply += `✅ Tất cả các chỉ số nông trường đang ở trạng thái an toàn tối ưu.`;
    }

    const resultPayload = {
      query_id: `QRY-${Date.now()}`,
      prompt,
      answer: reply,
      timestamp: Date.now(),
    };

    this.eventsGateway.broadcast('AI_CHAT_RESPONSE', resultPayload);
    return resultPayload;
  }

  // --- KAFKA PRODUCER HELPER METHODS ---

  public async publishRequest(
    promptOrObj: string | { prompt: string; session_id?: string },
    sessionId?: string,
  ): Promise<{ request_id: string; session_id: string; prompt: string }> {
    let prompt: string;
    let sessId: string;

    if (typeof promptOrObj === 'object' && promptOrObj !== null) {
      prompt = promptOrObj.prompt;
      sessId = promptOrObj.session_id || `SESS-${Date.now()}`;
    } else {
      prompt = String(promptOrObj);
      sessId = sessionId || `SESS-${Date.now()}`;
    }

    const requestId = `REQ-${Date.now()}`;
    const payload = {
      request_id: requestId,
      session_id: sessId,
      prompt,
      created_at: new Date().toISOString(),
      source: 'OPERATOR_WEB_UI',
    };

    await this.producer.send({
      topic: this.topicRequests,
      messages: [{ key: requestId, value: JSON.stringify(payload) }],
    });

    this.logger.log(`🚀 [PUBLISHED REQUEST] ID: ${requestId} -> ${this.topicRequests}`);
    return payload;
  }

  public async publishAction(topic: string, param1: any, param2?: any): Promise<void> {
    let key: string;
    let payload: any;

    if (param2 !== undefined) {
      key = String(param1);
      payload = param2;
    } else {
      payload = param1;
      key = String(payload?.plan_id || payload?.task_id || payload?.request_id || payload?.action || 'ACTION');
    }

    try {
      await this.producer.send({
        topic,
        messages: [{ key, value: JSON.stringify(payload) }],
      });
      this.logger.log(`🚀 [PUBLISHED ACTION] -> ${topic} [key=${key}]`);
    } catch (err: any) {
      this.logger.error(`Failed to publish action to ${topic}: ${err?.message}`);
    }
  }
}
