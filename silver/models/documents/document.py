# Copyright (c) 2017 Presslabs SRL
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from decimal import Decimal

from django.db import models

from .entries import DocumentEntry


class Document(models.Model):
    kind = models.CharField(max_length=40)

    def __init__(self, *args, **kwargs):
        self._entries = None
        super(Document, self).__init__(*args, **kwargs)

    @property
    def total(self):
        if self._total is not None:
            return self._total

        entries = self._get_entries()
        entries_total = [Decimal(entry.total) for entry in entries]

        return sum(entries_total)

    @property
    def total_in_transaction_currency(self):
        if self._total_in_transaction_currency is not None:
            return self._total_in_transaction_currency

        entries = self._get_entries()
        entries_total = [Decimal(entry.total_in_transaction_currency)
                         for entry in entries]

        return sum(entries_total)

    series = models.CharField(max_length=20, blank=True, null=True)
    number = models.IntegerField(blank=True, null=True)
    customer = models.ForeignKey('Customer')
    provider = models.ForeignKey('Provider')
    due_date = models.DateField(null=True, blank=True)
    issue_date = models.DateField(null=True, blank=True)
    paid_date = models.DateField(null=True, blank=True)
    cancel_date = models.DateField(null=True, blank=True)
    sales_tax_percent = models.DecimalField(max_digits=4, decimal_places=2,
                                            null=True, blank=True)
    sales_tax_name = models.CharField(max_length=64, blank=True, null=True)
    currency = models.CharField(max_length=4)
    transaction_currency = models.CharField(max_length=4)
    state = models.CharField(max_length=10)
    pdf = models.ForeignKey('PDF', null=True)

    _total = models.DecimalField(max_digits=19, decimal_places=2,
                                 null=True, blank=True)
    _total_in_transaction_currency = models.DecimalField(max_digits=19,
                                                         decimal_places=2,
                                                         null=True, blank=True)

    class Meta:
        managed = False

    def _get_entries(self):
        if self._entries is None:
            data = {
                'invoice_id': self.id
            } if self.kind == 'invoice' else {
                'proforma_id': self.id
            }

            self._entries = list(DocumentEntry.objects.filter(**data)
                                 .select_related('invoice', 'proforma').all())
        return self._entries
