import { Module } from '@nestjs/common';
import { TelemetryController } from './telemetry.controller';
import { KafkaModule } from '../kafka/kafka.module';
import { WebsocketModule } from '../websocket/websocket.module';

@Module({
  imports: [KafkaModule, WebsocketModule],
  controllers: [TelemetryController],
})
export class TelemetryModule {}
