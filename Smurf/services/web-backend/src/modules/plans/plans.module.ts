import { Module } from '@nestjs/common';
import { PlansController } from './plans.controller';
import { KafkaModule } from '../kafka/kafka.module';
import { WebsocketModule } from '../websocket/websocket.module';

@Module({
  imports: [KafkaModule, WebsocketModule],
  controllers: [PlansController],
})
export class PlansModule {}
