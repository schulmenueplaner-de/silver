# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('silver', '0036_auto_20170514_1627'),
    ]

    operations = [
        migrations.AddField(
            model_name='provider',
            name='transaction_maximum_automatic_retries',
            field=models.PositiveIntegerField(default=5),
        ),
        migrations.AddField(
            model_name='provider',
            name='transaction_retry_pattern',
            field=models.CharField(default=b'exponential', max_length=16, choices=[(b'exponential', b'Exponential'), (b'daily', b'Daily'), (b'fibonacci', b'Fibonacci')]),
        ),
        migrations.AddField(
            model_name='transaction',
            name='retrial_type',
            field=models.CharField(blank=True, max_length=16, null=True, choices=[(b'customer', 'Customer'), (b'payment_processor', 'Payment_processor'), (b'automatic', 'Automatic'), (b'staff', 'Staff')]),
        ),
        migrations.AddField(
            model_name='transaction',
            name='retried_transaction',
            field=models.OneToOneField(related_name='retried_by', null=True, blank=True, to='silver.Transaction'),
        ),
    ]
