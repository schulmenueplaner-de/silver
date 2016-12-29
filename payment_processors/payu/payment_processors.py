import payu

from payu import conf
# from payu.exceptions import (AuthenticationError, AuthorizationError,
#                              DownForMaintenanceError, ServerError,
#                              UpgradeRequiredError)

from django.utils import timezone
from django_fsm import TransitionNotAllowed

from silver.models.payment_processors.base import PaymentProcessorBase
from silver.models.payment_processors.mixins import TriggeredProcessorMixin

from .payment_methods import PayuPaymentMethod
from .views import PayuTransactionView


class PayuTriggered(PaymentProcessorBase, TriggeredProcessorMixin):
    view_class = PayuTransactionView
    payment_method_class = PayuPaymentMethod

    _has_been_setup = False

    def __init__(self, merchant_id, merchant_key, *args, **kwargs):
        if PayuTriggered._has_been_setup:
            return

        conf.Configuration.MERCHANT = merchant_id

        conf.Configuration.MERCHANT = merchant_id
        conf.Configuration.MERCHANT_KEY = merchant_key

        if 'test_transaction' in kwargs:
            conf.Configuration.TEST_TRANSACTION = kwargs['test_transaction']

        PayuTriggered._has_been_setup = True

        super(PayuTriggered, self).__init__(*args, **kwargs)

    @property
    def client_token(self):
        return None

    def refund_transaction(self, transaction, payment_method=None):
        pass

    def void_transaction(self, transaction, payment_method=None):
        pass

    def _update_payment_method(self, payment_method, result_payment_method):
        """
        :param payment_method: A PayuPaymentMethod.
        :param result_payment_method: A payment method from a payuSDK
                                      result(response).
        :description: Updates a given payment method's data with data from a
                      payuSDK result payment method.
        """

        payment_method_details = {
            'type': result_payment_method.__class__.__name__
        }

        if payment_method_details['type'] == payment_method.Type.PayPal:
            payment_method_details['email'] = result_payment_method.email
        elif payment_method_details['type'] == payment_method.Type.CreditCard:
            payment_method_details.update({
                'card_type': result_payment_method.card_type,
                'last_4': result_payment_method.last_4,
            })

        payment_method_details.update({
            'image_url': payment_method.image_url,
            'added_at': timezone.now().isoformat()
        })

        payment_method.data['details'] = payment_method_details

        try:
            if payment_method.is_recurring:
                if payment_method.state == payment_method.State.Unverified:
                    payment_method.verify({
                        'token': result_payment_method.token
                    })
            else:
                payment_method.disable()
        except TransitionNotAllowed:
            # TODO handle this
            pass

        payment_method.save()

    def _update_transaction_status(self, transaction, result_transaction):
        """
        :param payment_method: A Transaction.
        :param result_payment_method: A transaction from a payuSDK
                                      result(response).
        :description: Updates a given transaction's data with data from a
                      payuSDK result payment method.
        """

        if not transaction.data:
            transaction.data = {}

        transaction.data.update({
            'status': result_transaction.status,
            'payu_id': result_transaction.id
        })

        status = transaction.data['status']

        try:
            if status in [payu.Transaction.Status.AuthorizationExpired,
                          payu.Transaction.Status.SettlementDeclined,
                          payu.Transaction.Status.Failed,
                          payu.Transaction.Status.GatewayRejected,
                          payu.Transaction.Status.ProcessorDeclined]:
                if transaction.state != transaction.States.Failed:
                    transaction.fail()

            elif status == payu.Transaction.Status.Voided:
                if transaction.state != transaction.States.Canceled:
                    transaction.cancel()

            elif status in [payu.Transaction.Status.Authorizing,
                            payu.Transaction.Status.Authorized,
                            payu.Transaction.Status.SubmittedForSettlement,
                            payu.Transaction.Status.SettlementConfirmed]:
                if transaction.state != transaction.States.Pending:
                    transaction.process()

            elif status in [payu.Transaction.Status.Settling,
                            payu.Transaction.Status.SettlementPending,
                            payu.Transaction.Status.Settled]:
                if transaction.state != transaction.States.Settled:
                    transaction.settle()

        except TransitionNotAllowed:
            # TODO handle this (probably throw something else)
            pass

        transaction.save()

    def _charge_transaction(self, transaction):
        """
        :param transaction: The transaction to be charged. Must have a useable
                            payment_method.
        :return: True on success, False on failure.
        """

        payment_method = transaction.payment_method

        if not payment_method.is_usable:
            return False

        # prepare payload
        if payment_method.token:
            data = {'payment_method_token': payment_method.token}
        else:
            data = {'payment_method_nonce': payment_method.nonce}

        data.update({
            'amount': transaction.amount,
            'billing': {
                'postal_code': payment_method.data.get('postal_code')
            },
            'cardholder_name': payment_method.data.get('cardholder_name'),
            'options': {
                'submit_for_settlement': True,
                "store_in_vault_on_success": payment_method.is_recurring
            },
        })

        # send transaction request
        result = payu.Transaction.sale(data)

        # handle response
        if result.is_success and result.transaction:
            self._update_payment_method(payment_method,
                                        result.transaction.payment_method)

            self._update_transaction_status(transaction, result.transaction)

        return result.is_success

    def manage_transaction(self, transaction):
        """
        :param transaction: A Payu transaction in Initial or Pending state.
        :return: True on success, False on failure.
        """

        if not transaction.payment_processor == self:
            return False

        if transaction.state not in [transaction.States.Initial,
                                     transaction.States.Pending]:
            return False

        print transaction

        if transaction.data.get('payu_id'):
            try:
                result_transaction = payu.Transaction.find(
                    transaction.data['payu_id']
                )
            except payu.exceptions.NotFoundError:
                return False

            self._update_transaction_status(transaction, result_transaction)

            return True

        return self._charge_transaction(transaction)
