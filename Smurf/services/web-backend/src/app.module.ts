import { Module } from '@nestjs/common';
import { TelemetryModule } from './modules/telemetry/telemetry.module';
import { KafkaModule } from './modules/kafka/kafka.module';
import { WebsocketModule } from './modules/websocket/websocket.module';

@Module({
  imports: [KafkaModule, WebsocketModule, TelemetryModule],
})
export class AppModule {}
