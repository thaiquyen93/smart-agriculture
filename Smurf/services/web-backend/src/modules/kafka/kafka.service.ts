import { Injectable, OnModuleInit, OnModuleDestroy, Logger } from '@nestjs/common';
import { Kafka, Consumer, Producer } from 'kafkajs';
import { EventsGateway } from '../websocket/events.gateway';

@Injectable()
export class KafkaService implements OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger(KafkaService.name);
  private kafka: Kafka;
  private consumer: Consumer;
  private producer: Producer;

  private latestTelemetry: Map<string, any> = new Map();
  private latestForecasts: Map<string, any> = new Map();
  private latestPlans: Map<string, any> = new Map();
  private latestTasks: Map<string, any> = new Map();

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
      clientId: 'smurf-nestjs-backend',
      brokers,
    });
    this.consumer = this.kafka.consumer({ groupId: 'smurf-nestjs-backend-group' });
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
    await this.initKafka();
  }

  async onModuleDestroy() {
    try {
      await this.consumer.disconnect();
      await this.producer.disconnect();
    } catch (e) {
      this.logger.warn(`Error disconnecting Kafka: ${e.message}`);
    }
  }

  private async initKafka() {
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
        eachMessage: async ({ topic, message }) => {
          if (!message.value) return;
          try {
            const payload = JSON.parse(message.value.toString());
            const devId = payload.device_id || payload.device_code || payload.station_id || 'UNKNOWN';

            if (topic === this.topicRaw) {
              payload.device_id = devId;
              this.latestTelemetry.set(devId, payload);
              this.eventsGateway.broadcast('TELEMETRY_RAW', payload);
            } else if (topic === this.topicP) {
              this.eventsGateway.broadcast('WINDOW_MINUTE', payload);
            } else if (topic === this.topicH) {
              this.eventsGateway.broadcast('WINDOW_HOURLY', payload);
            } else if (topic === this.topicAlerts) {
              this.eventsGateway.broadcast('ALERT_EVENT', payload);
            } else if (topic === this.topicForecasts) {
              this.latestForecasts.set(devId, payload);
              this.eventsGateway.broadcast('AI_FORECAST', payload);
            } else if (topic === this.topicPlans) {
              const planId = payload.plan_id || `PLAN-${Date.now()}`;
              this.latestPlans.set(planId, payload);
              this.eventsGateway.broadcast('IRRIGATION_PLAN', payload);
            } else if (topic === this.topicTasks) {
              const taskId = payload.task_id || `TASK-${Date.now()}`;
              this.latestTasks.set(taskId, payload);
              this.eventsGateway.broadcast('INSPECTION_TASK', payload);
            } else if (topic === this.topicAgentLogs) {
              this.eventsGateway.broadcast('AGENT_LOG', payload);
            }
          } catch (err) {
            this.logger.error(`Error parsing message on ${topic}: ${err.message}`);
          }
        },
      });
    } catch (err) {
      this.logger.warn(`Kafka init failed: ${err.message}. Retrying in 3s...`);
      setTimeout(() => this.initKafka(), 3000);
    }
  }

  async publishRequest(request: { prompt: string; session_id?: string; request_id?: string }) {
    const reqPayload = {
      request_id: request.request_id || `REQ-${Date.now()}`,
      session_id: request.session_id || `SESS-${Date.now()}`,
      prompt: request.prompt,
      created_at: Date.now() / 1000,
    };

    try {
      await this.producer.send({
        topic: this.topicRequests,
        messages: [{ key: reqPayload.request_id, value: JSON.stringify(reqPayload) }],
      });
      this.logger.log(`🚀 [PUBLISHED REQUEST] ID: ${reqPayload.request_id} -> ${this.topicRequests}`);
      this.eventsGateway.broadcast('REQUEST_CREATED', reqPayload);
    } catch (err) {
      this.logger.error(`Failed to publish request: ${err.message}`);
      throw err;
    }

    return reqPayload;
  }

  async publishAction(topic: string, actionPayload: any) {
    try {
      await this.producer.send({
        topic,
        messages: [{ value: JSON.stringify(actionPayload) }],
      });
      this.logger.log(`🚀 [PUBLISHED ACTION] -> ${topic}`);
    } catch (err) {
      this.logger.error(`Failed to publish action to ${topic}: ${err.message}`);
    }
  }

  getLatestTelemetry(): any[] {
    return Array.from(this.latestTelemetry.values());
  }

  getLatestTelemetryMap(): Map<string, any> {
    return this.latestTelemetry;
  }

  getLatestForecasts(): any[] {
    return Array.from(this.latestForecasts.values());
  }
}
