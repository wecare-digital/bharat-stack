"""
Metrics Utility Module

Provides CloudWatch metrics emission for monitoring
message delivery rates, bulk job performance, and system health.

Requirements: 14.4, 14.5
"""

import os
import time
import logging
import boto3
from typing import Dict, Any, List, Optional
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Initialize CloudWatch client
_cloudwatch_client = None

def get_cloudwatch_client():
    """Get or create CloudWatch client singleton."""
    global _cloudwatch_client
    if _cloudwatch_client is None:
        _cloudwatch_client = boto3.client(
            'cloudwatch',
            region_name=os.environ.get('AWS_REGION', 'us-east-1')
        )
    return _cloudwatch_client


class MetricUnit(Enum):
    """CloudWatch metric units."""
    COUNT = "Count"
    SECONDS = "Seconds"
    MILLISECONDS = "Milliseconds"
    PERCENT = "Percent"
    BYTES = "Bytes"


@dataclass
class Metric:
    """CloudWatch metric data point."""
    name: str
    value: float
    unit: MetricUnit
    dimensions: Dict[str, str] = None
    timestamp: float = None

    def to_cloudwatch_format(self) -> Dict[str, Any]:
        """Convert to CloudWatch PutMetricData format."""
        metric_data = {
            'MetricName': self.name,
            'Value': self.value,
            'Unit': self.unit.value,
        }
        
        if self.dimensions:
            metric_data['Dimensions'] = [
                {'Name': k, 'Value': v}
                for k, v in self.dimensions.items()
            ]
        
        if self.timestamp:
            from datetime import datetime
            metric_data['Timestamp'] = datetime.fromtimestamp(self.timestamp)
        
        return metric_data


class MetricsEmitter:
    """
    CloudWatch metrics emitter for WECARE.DIGITAL platform.
    
    Emits custom metrics for:
    - Message delivery success/failure rates per channel
    - Bulk job processing duration and throughput
    - Rate limit usage
    - DLQ depth
    
    Requirements:
    - 14.4: Emit CloudWatch metrics for message delivery success/failure rates
    - 14.5: Emit CloudWatch metrics for bulk job processing duration and throughput
    """

    NAMESPACE = "WECARE.DIGITAL"
    
    def __init__(self, cloudwatch_client=None):
        """
        Initialize MetricsEmitter.
        
        Args:
            cloudwatch_client: Boto3 CloudWatch client (optional, uses default if not provided)
        """
        self.cloudwatch = cloudwatch_client or get_cloudwatch_client()
        self._metric_buffer: List[Metric] = []
        self._buffer_size = int(os.environ.get('METRICS_BUFFER_SIZE', 20))

    def emit_message_delivery_metric(
        self,
        channel: str,
        status: str,
        count: int = 1
    ) -> None:
        """
        Emit message delivery metric.
        
        Requirement 14.4: Emit CloudWatch metrics for message delivery
        success and failure rates per channel.
        
        Args:
            channel: Messaging channel (WHATSAPP, SMS, EMAIL)
            status: Delivery status (SUCCESS, FAILED, PENDING)
            count: Number of messages (default 1)
        """
        metric = Metric(
            name=f"Messages{status.capitalize()}",
            value=count,
            unit=MetricUnit.COUNT,
            dimensions={
                'Channel': channel,
                'Status': status
            },
            timestamp=time.time()
        )
        self._emit_metric(metric)
        
        # Also emit total messages metric
        total_metric = Metric(
            name="MessagesTotal",
            value=count,
            unit=MetricUnit.COUNT,
            dimensions={'Channel': channel},
            timestamp=time.time()
        )
        self._emit_metric(total_metric)

    def emit_bulk_job_metric(
        self,
        job_id: str,
        duration_seconds: float = None,
        throughput_per_second: float = None,
        total_recipients: int = None,
        sent_count: int = None,
        failed_count: int = None
    ) -> None:
        """
        Emit bulk job metrics.
        
        Requirement 14.5: Emit CloudWatch metrics for bulk job
        processing duration and throughput.
        
        Args:
            job_id: Bulk job ID
            duration_seconds: Total processing duration
            throughput_per_second: Messages processed per second
            total_recipients: Total number of recipients
            sent_count: Successfully sent count
            failed_count: Failed count
        """
        timestamp = time.time()
        
        if duration_seconds is not None:
            self._emit_metric(Metric(
                name="BulkJobDuration",
                value=duration_seconds,
                unit=MetricUnit.SECONDS,
                dimensions={'JobId': job_id},
                timestamp=timestamp
            ))
        
        if throughput_per_second is not None:
            self._emit_metric(Metric(
                name="BulkJobThroughput",
                value=throughput_per_second,
                unit=MetricUnit.COUNT,
                dimensions={'JobId': job_id},
                timestamp=timestamp
            ))
        
        if total_recipients is not None:
            self._emit_metric(Metric(
                name="BulkJobRecipients",
                value=total_recipients,
                unit=MetricUnit.COUNT,
                dimensions={'JobId': job_id},
                timestamp=timestamp
            ))
        
        if sent_count is not None:
            self._emit_metric(Metric(
                name="BulkJobSent",
                value=sent_count,
                unit=MetricUnit.COUNT,
                dimensions={'JobId': job_id},
                timestamp=timestamp
            ))
        
        if failed_count is not None:
            self._emit_metric(Metric(
                name="BulkJobFailed",
                value=failed_count,
                unit=MetricUnit.COUNT,
                dimensions={'JobId': job_id},
                timestamp=timestamp
            ))
        
        # Calculate success rate if both counts available
        if sent_count is not None and failed_count is not None:
            total = sent_count + failed_count
            if total > 0:
                success_rate = (sent_count / total) * 100
                self._emit_metric(Metric(
                    name="BulkJobSuccessRate",
                    value=success_rate,
                    unit=MetricUnit.PERCENT,
                    dimensions={'JobId': job_id},
                    timestamp=timestamp
                ))

    def emit_validation_failure_metric(
        self,
        channel: str,
        reason: str
    ) -> None:
        """
        Emit validation failure metric.
        
        Args:
            channel: Messaging channel
            reason: Failure reason (OPT_IN_REQUIRED, ALLOWLIST_VIOLATION, etc.)
        """
        self._emit_metric(Metric(
            name="ValidationFailures",
            value=1,
            unit=MetricUnit.COUNT,
            dimensions={
                'Channel': channel,
                'Reason': reason
            },
            timestamp=time.time()
        ))

    def emit_rate_limit_metric(
        self,
        channel: str,
        usage_percent: float
    ) -> None:
        """
        Emit rate limit usage metric.
        
        Args:
            channel: Messaging channel
            usage_percent: Current usage as percentage of limit
        """
        self._emit_metric(Metric(
            name="RateLimitUsage",
            value=usage_percent,
            unit=MetricUnit.PERCENT,
            dimensions={'Channel': channel},
            timestamp=time.time()
        ))

    def emit_dlq_depth_metric(
        self,
        queue_name: str,
        depth: int
    ) -> None:
        """
        Emit DLQ depth metric.
        
        Args:
            queue_name: DLQ name
            depth: Number of messages in queue
        """
        self._emit_metric(Metric(
            name="DLQDepth",
            value=depth,
            unit=MetricUnit.COUNT,
            dimensions={'QueueName': queue_name},
            timestamp=time.time()
        ))

    def emit_api_latency_metric(
        self,
        service: str,
        operation: str,
        latency_ms: float
    ) -> None:
        """
        Emit API latency metric.
        
        Args:
            service: AWS service name
            operation: API operation name
            latency_ms: Latency in milliseconds
        """
        self._emit_metric(Metric(
            name="APILatency",
            value=latency_ms,
            unit=MetricUnit.MILLISECONDS,
            dimensions={
                'Service': service,
                'Operation': operation
            },
            timestamp=time.time()
        ))

    def emit_tier_limit_metric(
        self,
        tier: int,
        usage_count: int,
        limit: int
    ) -> None:
        """
        Emit WhatsApp tier limit usage metric.
        
        Args:
            tier: Current WhatsApp business tier
            usage_count: Current conversation count
            limit: Tier limit
        """
        usage_percent = (usage_count / limit * 100) if limit > 0 else 0
        
        self._emit_metric(Metric(
            name="WhatsAppTierUsage",
            value=usage_count,
            unit=MetricUnit.COUNT,
            dimensions={'Tier': str(tier)},
            timestamp=time.time()
        ))
        
        self._emit_metric(Metric(
            name="WhatsAppTierUsagePercent",
            value=usage_percent,
            unit=MetricUnit.PERCENT,
            dimensions={'Tier': str(tier)},
            timestamp=time.time()
        ))

    def _emit_metric(self, metric: Metric) -> None:
        """Add metric to buffer and flush if needed."""
        self._metric_buffer.append(metric)
        
        if len(self._metric_buffer) >= self._buffer_size:
            self.flush()

    def flush(self) -> None:
        """Flush buffered metrics to CloudWatch."""
        if not self._metric_buffer:
            return
        
        if not self.cloudwatch:
            # Log metrics locally if no CloudWatch client
            for metric in self._metric_buffer:
                logger.info(f"Metric: {metric.name}={metric.value} {metric.unit.value} {metric.dimensions}")
            self._metric_buffer.clear()
            return
        
        try:
            # Convert to CloudWatch format
            metric_data = [m.to_cloudwatch_format() for m in self._metric_buffer]
            
            # CloudWatch allows max 20 metrics per call
            for i in range(0, len(metric_data), 20):
                batch = metric_data[i:i+20]
                self.cloudwatch.put_metric_data(
                    Namespace=self.NAMESPACE,
                    MetricData=batch
                )
            
            self._metric_buffer.clear()
            
        except Exception as e:
            logger.error(f"Failed to emit metrics: {str(e)}")
            # Keep metrics in buffer for retry


    def emit_authentication_metric(
        self,
        result: str,
        role: str = None
    ) -> None:
        """
        Emit authentication metric.
        
        Requirement 14.1: Log all authentication attempts
        
        Args:
            result: Authentication result (SUCCESS, FAILED, UNAUTHORIZED)
            role: User role if authentication succeeded
        """
        dimensions = {'Result': result}
        if role:
            dimensions['Role'] = role
            
        self._emit_metric(Metric(
            name="AuthenticationAttempts",
            value=1,
            unit=MetricUnit.COUNT,
            dimensions=dimensions,
            timestamp=time.time()
        ))

    def emit_lambda_invocation_metric(
        self,
        function_name: str,
        duration_ms: float,
        success: bool
    ) -> None:
        """
        Emit Lambda invocation metric.
        
        Args:
            function_name: Lambda function name
            duration_ms: Execution duration in milliseconds
            success: Whether invocation succeeded
        """
        self._emit_metric(Metric(
            name="LambdaInvocations",
            value=1,
            unit=MetricUnit.COUNT,
            dimensions={
                'FunctionName': function_name,
                'Status': 'SUCCESS' if success else 'FAILED'
            },
            timestamp=time.time()
        ))
        
        self._emit_metric(Metric(
            name="LambdaDuration",
            value=duration_ms,
            unit=MetricUnit.MILLISECONDS,
            dimensions={'FunctionName': function_name},
            timestamp=time.time()
        ))

    def emit_error_metric(
        self,
        error_type: str,
        function_name: str
    ) -> None:
        """
        Emit error metric.
        
        Args:
            error_type: Type of error
            function_name: Lambda function where error occurred
        """
        self._emit_metric(Metric(
            name="Errors",
            value=1,
            unit=MetricUnit.COUNT,
            dimensions={
                'ErrorType': error_type,
                'FunctionName': function_name
            },
            timestamp=time.time()
        ))


# Global metrics emitter instance
_metrics_emitter = None

def get_metrics_emitter() -> MetricsEmitter:
    """Get or create global MetricsEmitter instance."""
    global _metrics_emitter
    if _metrics_emitter is None:
        _metrics_emitter = MetricsEmitter()
    return _metrics_emitter


# SNS Alert Publisher
class AlertPublisher:
    """
    SNS alert publisher for critical errors and warnings.
    
    Requirement 14.7: Publish alerts to SNS Topic
    """
    
    SNS_TOPIC_ARN = os.environ.get(
        'SNS_ALERT_TOPIC',
        'arn:aws:sns:us-east-1:775261844268:base-wecare-digital'
    )
    
    def __init__(self, sns_client=None):
        """Initialize AlertPublisher."""
        self.sns = sns_client or boto3.client(
            'sns',
            region_name=os.environ.get('AWS_REGION', 'us-east-1')
        )
    
    def publish_critical_error(
        self,
        error_type: str,
        message: str,
        details: Dict[str, Any] = None
    ) -> None:
        """
        Publish critical error alert.
        
        Requirement 14.7: Publish alerts on critical errors
        """
        self._publish_alert(
            subject=f"[CRITICAL] WECARE.DIGITAL: {error_type}",
            message=message,
            details=details,
            severity='CRITICAL'
        )
    
    def publish_tier_limit_warning(
        self,
        current_usage: int,
        limit: int,
        usage_percent: float
    ) -> None:
        """
        Publish WhatsApp tier limit warning.
        
        Requirement 13.9: Alert when tier limit reaches 80%
        """
        if usage_percent >= 80:
            self._publish_alert(
                subject=f"[WARNING] WECARE.DIGITAL: WhatsApp Tier Limit at {usage_percent:.1f}%",
                message=f"WhatsApp business tier limit approaching. Current usage: {current_usage}/{limit} ({usage_percent:.1f}%)",
                details={
                    'currentUsage': current_usage,
                    'limit': limit,
                    'usagePercent': usage_percent
                },
                severity='WARNING'
            )
    
    def publish_dlq_depth_warning(
        self,
        queue_name: str,
        depth: int
    ) -> None:
        """
        Publish DLQ depth warning.
        
        Alert when DLQ depth exceeds threshold
        """
        if depth > 10:
            self._publish_alert(
                subject=f"[WARNING] WECARE.DIGITAL: DLQ Depth Alert - {queue_name}",
                message=f"Dead Letter Queue '{queue_name}' has {depth} messages pending",
                details={
                    'queueName': queue_name,
                    'depth': depth
                },
                severity='WARNING'
            )
    
    def _publish_alert(
        self,
        subject: str,
        message: str,
        details: Dict[str, Any] = None,
        severity: str = 'INFO'
    ) -> None:
        """Publish alert to SNS topic."""
        try:
            import json
            
            alert_body = {
                'severity': severity,
                'message': message,
                'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                'environment': os.environ.get('ENVIRONMENT', 'unknown'),
                'details': details or {}
            }
            
            self.sns.publish(
                TopicArn=self.SNS_TOPIC_ARN,
                Subject=subject[:100],  # SNS subject limit
                Message=json.dumps(alert_body, indent=2)
            )
            
            logger.info(f"Alert published: {subject}")
            
        except Exception as e:
            logger.error(f"Failed to publish alert: {str(e)}")


# Global alert publisher instance
_alert_publisher = None

def get_alert_publisher() -> AlertPublisher:
    """Get or create global AlertPublisher instance."""
    global _alert_publisher
    if _alert_publisher is None:
        _alert_publisher = AlertPublisher()
    return _alert_publisher
