import { Controller, Get } from '@nestjs/common';
import { KafkaService } from '../kafka/kafka.service';
import { EventsGateway } from '../websocket/events.gateway';

@Controller('api/v1')
export class TelemetryController {
  constructor(
    private readonly kafkaService: KafkaService,
    private readonly eventsGateway: EventsGateway,
  ) {}

  @Get('health')
  getHealth() {
    return {
      status: 'OK',
      service: 'Smurf NestJS Modular Backend',
      timestamp: Date.now(),
      webSocketsClients: this.eventsGateway.getClientCount(),
    };
  }

  @Get('telemetry/latest')
  getLatestTelemetry() {
    return this.kafkaService.getLatestTelemetry();
  }

  @Get('forecasts/latest')
  getLatestForecasts() {
    return this.kafkaService.getLatestForecasts();
  }
}
