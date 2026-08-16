import { Injectable, OnModuleInit, OnModuleDestroy } from '@nestjs/common';
import { Kafka, Consumer } from 'kafkajs';
import { EventsGateway } from '../websocket/events.gateway';

@Injectable()
export class KafkaService implements OnModuleInit, OnModuleDestroy {
  private kafka: Kafka;
  private consumer: Consumer;
  private latestTelemetry: Map<string, any> = new Map();
  private latestForecasts: Map<string, any> = new Map();

  constructor(private readonly eventsGateway: EventsGateway) {
    const brokers = (process.env.KAFKA_BOOTSTRAP_SERVERS || 'localhost:9092').split(',');
    this.kafka = new Kafka({
      clientId: 'smurf-nestjs-backend',
      brokers,
    });
    this.consumer = this.kafka.consumer({ groupId: 'smurf-nestjs-backend-group' });
  }

  async onModuleInit() {
    await this.initKafka();
  }

  async onModuleDestroy() {
    await this.consumer.disconnect();
  }

  private async initKafka() {
    const topicRaw = process.env.TOPIC_RAW || 'topic_raw';
    const topicP = process.env.TOPIC_P || 'topic_p';
    const topicH = process.env.TOPIC_H || 'topic_h';
    const topicAlerts = process.env.TOPIC_ALERTS || 'topic_alerts';
    const topicForecasts = process.env.TOPIC_FORECASTS || 'topic_forecasts';
    const topicIrrigation = process.env.TOPIC_IRRIGATION_PLANS || 'topic_irrigation_plans';
    const topicInspection = process.env.TOPIC_INSPECTION_TASKS || 'topic_inspection_tasks';
    const topicAgentLogs = process.env.TOPIC_AGENT_LOGS || 'topic_agent_logs';

    try {
      await this.consumer.connect();
      console.log('[NestJS KafkaService] Connected to Redpanda Kafka');

      await this.consumer.subscribe({
        topics: [topicRaw, topicP, topicH, topicAlerts, topicForecasts, topicIrrigation, topicInspection, topicAgentLogs],
        fromBeginning: false,
      });

      await this.consumer.run({
        eachMessage: async ({ topic, message }) => {
          if (!message.value) return;
          try {
            const payload = JSON.parse(message.value.toString());

            if (topic === topicRaw) {
              const devId = payload.device_id || payload.device_code || payload.station_id || 'UNKNOWN';
              this.latestTelemetry.set(devId, payload);
              this.eventsGateway.broadcast('TELEMETRY_RAW', payload);
            } else if (topic === topicP) {
              this.eventsGateway.broadcast('WINDOW_MINUTE', payload);
            } else if (topic === topicH) {
              this.eventsGateway.broadcast('WINDOW_HOURLY', payload);
            } else if (topic === topicAlerts) {
              this.eventsGateway.broadcast('ALERT_EVENT', payload);
            } else if (topic === topicForecasts) {
              this.latestForecasts.set(payload.station_id || 'STN_UNKNOWN', payload);
              this.eventsGateway.broadcast('AI_FORECAST', payload);
            } else if (topic === topicIrrigation) {
              this.eventsGateway.broadcast('IRRIGATION_PLAN', payload);
            } else if (topic === topicInspection) {
              this.eventsGateway.broadcast('INSPECTION_TASK', payload);
            } else if (topic === topicAgentLogs) {
              this.eventsGateway.broadcast('AGENT_LOG', payload);
            }
          } catch (err) {
            console.error(`[NestJS Kafka] Error parsing message on ${topic}:`, err);
          }
        },
      });
    } catch (err) {
      console.warn(`[NestJS Kafka] Connection failed: ${err}. Retrying in 3s...`);
      setTimeout(() => this.initKafka(), 3000);
    }
  }

  getLatestTelemetry() {
    return Array.from(this.latestTelemetry.values());
  }

  getLatestForecasts() {
    return Array.from(this.latestForecasts.values());
  }
}
