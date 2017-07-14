import logging
from itertools import chain

from celery import group
from django.conf import settings
from django.db.models import Q
from redis.exceptions import LockError

from silver.models import Invoice, Proforma, Transaction, PaymentMethod
from silver.vendors.celery_app import task
from silver.vendors.redis_server import redis


logger = logging.getLogger(__name__)


@task()
def generate_pdf(document_id, document_type):
    if document_type == 'Invoice':
        document = Invoice.objects.get(id=document_id)
    else:
        document = Proforma.objects.get(id=document_id)

    document.generate_pdf()


PDF_GENERATION_TIME_LIMIT = getattr(settings, 'PDF_GENERATION_TIME_LIMIT', 60)


@task(time_limit=PDF_GENERATION_TIME_LIMIT, ignore_result=True)
def generate_pdfs():
    lock = redis.lock('reconcile_new_domains_without_cert', timeout=PDF_GENERATION_TIME_LIMIT)

    if not lock.acquire(blocking=False):
        return

    dirty_documents = chain(Invoice.objects.filter(pdf__dirty=True),
                            Proforma.objects.filter(pdf__dirty=True))

    # Generate PDFs in parallel
    group(generate_pdf.s(document.id, document.kind)
          for document in dirty_documents)()

    try:
        lock.release()
    except LockError:
        pass


@task()
def retry_transactions():
    for transaction in Transaction.objects.filter(Q(invoice__state=Invoice.STATES.ISSUED) |
                                                  Q(proforma__state=Proforma.STATES.ISSUED),
                                                  state=Transaction.States.Failed,
                                                  retried_by=None):
        if not transaction.should_be_retried:
            continue

        for payment_method in PaymentMethod.objects.filter(customer=transaction.customer,
                                                           verified=True, canceled=False):
            try:
                transaction.retry(payment_method=payment_method)
                break
            except Exception:
                logger.exception('[Tasks][Transaction]: %s', {
                    'detail': 'There was an error while retrying the transaction.',
                    'transaction_id': transaction.id
                })
