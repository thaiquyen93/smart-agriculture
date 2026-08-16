import { Module } from '@nestjs/common';
import { KafkaService } from './kafka.service';
import { WebsocketModule } from '../websocket/websocket.module';

@Module({
  imports: [WebsocketModule],
  providers: [KafkaService],
  exports: [KafkaService],
})
export class KafkaModule {}
