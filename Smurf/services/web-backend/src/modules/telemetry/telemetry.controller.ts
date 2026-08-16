import { Controller, Get } from '@nestjs/common';
import { KafkaService } from '../kafka/kafka.service';
import { EventsGateway } from '../websocket/events.gateway';
import { DbService } from '../db/db.service';

@Controller('api/v1')
export class TelemetryController {
  constructor(
    private readonly kafkaService: KafkaService,
    private readonly eventsGateway: EventsGateway,
    private readonly dbService: DbService,
  ) {}

  @Get('health')
  getHealth() {
    return {
      status: 'OK',
      service: 'Smurf Smart Agriculture Backend',
      timestamp: Date.now(),
      webSocketsClients: this.eventsGateway.getClientCount(),
      track: 'Track B: Smart Agriculture',
    };
  }

  @Get('telemetry/latest')
  getLatestTelemetry() {
    const memoryMap = this.kafkaService.getLatestTelemetryMap();
    const dbStates = this.dbService.getLatestDeviceStates();

    const expectedDevices = ['SOIL_01', 'WEATHER_01', 'PUMP_01', 'PH_01', 'TANK_01', 'SUN_01'];
    const nowMs = Date.now();

    return expectedDevices.map((code) => {
      const live = memoryMap.get(code) || dbStates[code] || null;

      if (!live) {
        return {
          device_code: code,
          device_id: code,
          status: 'OFFLINE',
          is_stale: true,
          age_sec: 999999,
          payload: {},
        };
      }

      // Calculate freshness
      const eventTimeSec = live.event_time || live.timestamp || live.created_at || live.db_created_at || (nowMs / 1000);
      const eventTimeMs = eventTimeSec > 1e11 ? eventTimeSec : eventTimeSec * 1000;
      const ageSec = Math.max(0, Math.floor((nowMs - eventTimeMs) / 1000));
      const isStale = ageSec > 120; // Stale if > 2 minutes without updates

      return {
        device_code: code,
        device_id: code,
        name: live.name || code,
        age_sec: ageSec,
        is_stale: isStale,
        status: isStale ? 'STALE' : 'ONLINE',
        last_updated: new Date(eventTimeMs).toISOString(),
        metrics: {
          soil_moisture: live.soil_moisture,
          temperature: live.temperature,
          humidity: live.humidity,
          flow_rate: live.flow_rate,
          power: live.power,
          ph: live.ph,
          level: live.level,
          lux: live.lux,
          pump_status: live.status,
        },
        raw: live,
      };
    });
  }

  @Get('devices')
  getDevices() {
    return this.getLatestTelemetry();
  }

  @Get('forecasts/latest')
  getLatestForecasts() {
    return this.kafkaService.getLatestForecasts();
  }
}
