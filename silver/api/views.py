import datetime
from django.utils.encoding import force_text
from django_filters import FilterSet, CharFilter, BooleanFilter

from rest_framework import generics, permissions, status, filters
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_bulk import ListBulkCreateAPIView
from rest_framework_extensions.cache.decorators import cache_response

from rest_framework_extensions.cache.mixins import (ListCacheResponseMixin,
                                                    RetrieveCacheResponseMixin)
from rest_framework_extensions.key_constructor import bits, constructors
from django.core.cache import cache

from silver.api.dateutils import last_date_that_fits

from silver.models import (MeteredFeatureUnitsLog, Subscription, MeteredFeature,
                           Customer, Plan, Provider)
from silver.api.serializers import (MeteredFeatureUnitsLogSerializer,
                                    CustomerSerializer, SubscriptionSerializer,
                                    SubscriptionDetailSerializer,
                                    PlanSerializer, MeteredFeatureSerializer,
                                    ProviderSerializer)
from silver.utils import get_object_or_None


class UpdatedAtKeyBit(bits.KeyBitBase):
    def get_data(self, **kwargs):
        key = 'api_updated_at_timestamp'
        value = cache.get(key, None)
        if not value:
            value = datetime.datetime.utcnow()
            cache.set(key, value=value)
        return force_text(value)


class CustomKeyConstructor(constructors.DefaultKeyConstructor):
    updated_at = UpdatedAtKeyBit()


class CustomObjectKeyConstructor(constructors.DefaultKeyConstructor):
    retrieve_sql = bits.RetrieveSqlQueryKeyBit()
    updated_at = UpdatedAtKeyBit()


class CustomListKeyConstructor(constructors.DefaultKeyConstructor):
    list_sql = bits.ListSqlQueryKeyBit()
    pagination = bits.PaginationKeyBit()
    updated_at = UpdatedAtKeyBit()


class PlanFilter(FilterSet):
    name = CharFilter(name='name', lookup_type='icontains')
    currency = CharFilter(name='currency', lookup_type='icontains')
    enabled = BooleanFilter(name='enabled', lookup_type='iexact')
    private = BooleanFilter(name='private', lookup_type='iexact')
    interval = CharFilter(name='interval', lookup_type='icontains')
    product_code = CharFilter(name='product_code', lookup_type='icontains')
    provider = CharFilter(name='provider__company', lookup_type='icontains')

    class Meta:
        model = Plan
        fields = ['name', 'currency', 'enabled', 'private', 'product_code',
                  'currency', 'provider', 'interval']


class PlanList(generics.ListCreateAPIView):
    permission_classes = (permissions.IsAuthenticated, permissions.IsAdminUser,)
    serializer_class = PlanSerializer
    queryset = Plan.objects.all()
    filter_backends = (filters.DjangoFilterBackend,)
    filter_class = PlanFilter

    @cache_response(key_func=CustomListKeyConstructor())
    def get(self, request, *args, **kwargs):
        return super(PlanList, self).get(request, *args, **kwargs)


class PlanDetail(generics.RetrieveDestroyAPIView, RetrieveCacheResponseMixin):
    permission_classes = (permissions.IsAuthenticated, permissions.IsAdminUser,)
    serializer_class = PlanSerializer
    queryset = Plan.objects.all()

    @cache_response(key_func=CustomObjectKeyConstructor())
    def get(self, request, *args, **kwargs):
        return super(PlanDetail, self).get(request, *args, **kwargs)

    def get_object(self):
        pk = self.kwargs.get('pk', None)
        return get_object_or_404(Plan, pk=pk, enabled=True)

    def patch(self, request, *args, **kwargs):
        plan = get_object_or_404(Plan.objects, pk=self.kwargs.get('pk', None))
        name = request.data.get('name', None)
        generate_after = request.data.get('generate_after', None)
        due_days = request.data.get('due_days', None)
        plan.name = name or plan.name
        plan.generate_after = generate_after or plan.generate_after
        plan.due_days = due_days or plan.due_days
        plan.save()
        return Response(PlanSerializer(plan, context={'request': request}).data,
                        status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):
        plan = get_object_or_404(Plan.objects, pk=self.kwargs.get('pk', None))
        plan.enabled = False
        plan.save()
        return Response({"deleted": not plan.enabled},
                        status=status.HTTP_200_OK)


class PlanMeteredFeatures(generics.ListAPIView):
    permission_classes = (permissions.IsAuthenticated, permissions.IsAdminUser,)
    serializer_class = MeteredFeatureSerializer
    queryset = MeteredFeature.objects.all()

    @cache_response(key_func=CustomListKeyConstructor())
    def get(self, request, *args, **kwargs):
        return super(PlanMeteredFeatures, self).get(request, *args, **kwargs)

    def get_queryset(self):
        plan = get_object_or_None(Plan, pk=self.kwargs['pk'])
        return plan.metered_features.all() if plan else None


class MeteredFeaturesFilter(FilterSet):
    name = CharFilter(name='name', lookup_type='icontains')

    class Meta:
        model = MeteredFeature
        fields = ('name', )


class MeteredFeatureList(ListBulkCreateAPIView):
    permission_classes = (permissions.IsAuthenticated, permissions.IsAdminUser,)
    serializer_class = MeteredFeatureSerializer
    queryset = MeteredFeature.objects.all()
    filter_backends = (filters.DjangoFilterBackend,)
    filter_class = MeteredFeaturesFilter

    @cache_response(key_func=CustomListKeyConstructor())
    def get(self, request, *args, **kwargs):
        return super(MeteredFeatureList, self).get(request, *args, **kwargs)


class MeteredFeatureDetail(generics.RetrieveAPIView):
    permission_classes = (permissions.IsAuthenticated, permissions.IsAdminUser,)
    serializer_class = MeteredFeatureSerializer
    queryset = MeteredFeature.objects.all()

    def get_object(self):
        pk = self.kwargs.get('pk', None)
        return get_object_or_404(MeteredFeature, pk=pk)

    @cache_response(key_func=CustomObjectKeyConstructor())
    def get(self, request, *args, **kwargs):
        return super(MeteredFeatureDetail, self).get(request, *args, **kwargs)


class SubscriptionFilter(FilterSet):
    plan = CharFilter(name='plan__name', lookup_type='icontains')
    customer = CharFilter(name='customer__name', lookup_type='icontains')
    company = CharFilter(name='customer__company', lookup_type='icontains')

    class Meta:
        model = Subscription
        fields = ['plan', 'customer', 'company']


class SubscriptionList(generics.ListCreateAPIView):
    permission_classes = (permissions.IsAuthenticated, permissions.IsAdminUser,)
    queryset = Subscription.objects.all()
    serializer_class = SubscriptionSerializer
    filter_backends = (filters.DjangoFilterBackend,)
    filter_class = SubscriptionFilter

    @cache_response(key_func=CustomListKeyConstructor())
    def get(self, request, *args, **kwargs):
        return super(SubscriptionList, self).get(request, *args, **kwargs)


class SubscriptionDetail(generics.RetrieveAPIView):
    permission_classes = (permissions.IsAuthenticated, permissions.IsAdminUser,)
    queryset = Subscription.objects.all()
    serializer_class = SubscriptionDetailSerializer

    def get_object(self):
        pk = self.kwargs.get('pk', None)
        return get_object_or_404(Subscription, pk=pk)

    @cache_response(key_func=CustomObjectKeyConstructor())
    def get(self, request, *args, **kwargs):
        return super(SubscriptionDetail, self).get(request, *args, **kwargs)


class SubscriptionDetailActivate(APIView):
    permission_classes = (permissions.IsAuthenticated, permissions.IsAdminUser,)

    def post(self, request, *args, **kwargs):
        sub = get_object_or_404(Subscription.objects,
                                pk=self.kwargs.get('sub', None))
        if sub.state != 'inactive':
            message = 'Cannot activate subscription from %s state.' % sub.state
            return Response({"error": message},
                            status=status.HTTP_400_BAD_REQUEST)
        else:
            if request.POST.get('_content', None):
                start_date = request.data.get('start_date', None)
                trial_end = request.data.get('trial_end_date', None)
                sub.activate(start_date=start_date, trial_end_date=trial_end)
                sub.save()
            else:
                sub.activate()
                sub.save()
            return Response({"state": sub.state},
                            status=status.HTTP_200_OK)


class SubscriptionDetailCancel(APIView):
    permission_classes = (permissions.IsAuthenticated, permissions.IsAdminUser,)

    def post(self, request, *args, **kwargs):
        sub = get_object_or_404(Subscription.objects,
                                pk=self.kwargs.get('sub', None))
        when = request.data.get('when', None)
        if sub.state != 'active':
            message = 'Cannot cancel subscription from %s state.' % sub.state
            return Response({"error": message},
                            status=status.HTTP_400_BAD_REQUEST)
        else:
            if when == 'now':
                sub.cancel()
                sub.end()
                sub.save()
                return Response({"state": sub.state},
                                status=status.HTTP_200_OK)
            elif when == 'end_of_billing_cycle':
                sub.cancel()
                sub.save()
                return Response({"state": sub.state},
                                status=status.HTTP_200_OK)
            else:
                return Response(status=status.HTTP_400_BAD_REQUEST)


class SubscriptionDetailReactivate(APIView):
    permission_classes = (permissions.IsAuthenticated, permissions.IsAdminUser,)

    def post(self, request, *args, **kwargs):
        sub = get_object_or_404(Subscription.objects,
                                pk=self.kwargs.get('sub', None))
        if sub.state != 'canceled':
            msg = 'Cannot reactivate subscription from %s state.' % sub.state
            return Response({"error": msg},
                            status=status.HTTP_400_BAD_REQUEST)
        else:
            sub.activate()
            sub.save()
            return Response({"state": sub.state},
                            status=status.HTTP_200_OK)


class MeteredFeatureUnitsLogList(APIView):
    permission_classes = (permissions.IsAuthenticated, permissions.IsAdminUser,)
    paginate_by = None

    @cache_response(key_func=CustomKeyConstructor())
    def get(self, request, format=None, **kwargs):
        metered_feature_pk = kwargs.get('mf', None)
        subscription_pk = kwargs.get('sub', None)
        logs = MeteredFeatureUnitsLog.objects.filter(
            metered_feature=metered_feature_pk,
            subscription=subscription_pk)
        serializer = MeteredFeatureUnitsLogSerializer(
            logs, many=True, context={'request': request}
        )
        return Response(serializer.data)

    def patch(self, request, *args, **kwargs):
        metered_feature_pk = self.kwargs['mf']
        subscription_pk = self.kwargs['sub']
        date = request.data.get('date', None)
        consumed_units = request.data.get('count', None)
        update_type = request.data.get('update_type', None)
        if subscription_pk and metered_feature_pk:
            subscription = get_object_or_None(Subscription, pk=subscription_pk)
            metered_feature = get_object_or_None(MeteredFeature,
                                                 pk=metered_feature_pk)

            if subscription and metered_feature:
                if subscription.state != 'active':
                    return Response({"detail": "Subscription is not active"},
                                    status=status.HTTP_403_FORBIDDEN)
                if date and consumed_units is not None and update_type:
                    try:
                        date = datetime.datetime.strptime(date,
                                                          '%Y-%m-%d').date()
                        csd = subscription.current_start_date
                        ced = subscription.current_end_date

                        if date <= csd:
                            csdt = datetime.datetime.combine(csd, datetime.time())
                            allowed_time = datetime.timedelta(
                                seconds=subscription.plan.generate_after)
                            if datetime.datetime.now() < csdt + allowed_time:
                                ced = csd - datetime.timedelta(days=1)
                                csd = last_date_that_fits(
                                    initial_date=subscription.start_date,
                                    end_date=ced,
                                    interval_type=subscription.plan.interval,
                                    interval_count=subscription.plan.interval_count
                                )

                        if csd <= date <= ced:
                            if metered_feature not in \
                                    subscription.plan.metered_features.all():
                                err = "The metered feature does not belong to "\
                                      "the subscription's plan."
                                return Response(
                                    {"detail": err},
                                    status=status.HTTP_400_BAD_REQUEST
                                )
                            try:
                                log = MeteredFeatureUnitsLog.objects.get(
                                    start_date=csd,
                                    end_date=ced,
                                    metered_feature=metered_feature_pk,
                                    subscription=subscription_pk
                                )
                                if update_type == 'absolute':
                                    log.consumed_units = consumed_units
                                elif update_type == 'relative':
                                    log.consumed_units += consumed_units
                                log.save()
                            except MeteredFeatureUnitsLog.DoesNotExist:
                                log = MeteredFeatureUnitsLog.objects.create(
                                    metered_feature=metered_feature,
                                    subscription=subscription,
                                    start_date=subscription.current_start_date,
                                    end_date=subscription.current_end_date,
                                    consumed_units=consumed_units
                                )
                            finally:
                                return Response({"count": log.consumed_units},
                                                status=status.HTTP_200_OK)
                        else:
                            return Response({"detail": "Date is out of bounds"},
                                            status=status.HTTP_400_BAD_REQUEST)
                    except TypeError:
                        return Response({"detail": "Invalid date format"},
                                        status=status.HTTP_400_BAD_REQUEST)
                else:
                    return Response({"detail": "Not enough information provided"},
                                    status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({"detail": "Not found"},
                                status=status.HTTP_404_NOT_FOUND)
        return Response({"detail": "Wrong address"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CustomerFilter(FilterSet):
    active = BooleanFilter(name='is_active', lookup_type='iexact')
    email = CharFilter(name='email', lookup_type='icontains')
    company = CharFilter(name='company', lookup_type='icontains')
    name = CharFilter(name='name', lookup_type='icontains')
    country = CharFilter(name='country', lookup_type='icontains')
    sales_tax_name = CharFilter(name='sales_tax_name', lookup_type='icontains')

    class Meta:
        model = Customer
        fields = ['email', 'name', 'company', 'active', 'country', 'sales_tax_name']


class CustomerList(generics.ListCreateAPIView):
    permission_classes = (permissions.IsAuthenticated, permissions.IsAdminUser,)
    serializer_class = CustomerSerializer
    queryset = Customer.objects.all()
    filter_backends = (filters.DjangoFilterBackend,)
    filter_class = CustomerFilter

    @cache_response(key_func=CustomListKeyConstructor())
    def get(self, request, *args, **kwargs):
        return super(CustomerList, self).get(request, *args, **kwargs)


class CustomerDetail(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = (permissions.IsAuthenticated, permissions.IsAdminUser,)
    serializer_class = CustomerSerializer
    queryset = Customer.objects.all()

    def get_object(self):
        pk = self.kwargs.get('pk', None)
        return get_object_or_404(Customer, pk=pk)

    @cache_response(key_func=CustomObjectKeyConstructor())
    def get(self, request, *args, **kwargs):
        return super(CustomerDetail, self).get(request, *args, **kwargs)


class ProviderFilter(FilterSet):
    email = CharFilter(name='email', lookup_type='icontains')
    company = CharFilter(name='company', lookup_type='icontains')

    class Meta:
        model = Provider
        fields = ['email', 'company']


class ProviderListBulkCreate(ListBulkCreateAPIView):
    permission_classes = (permissions.IsAuthenticated, permissions.IsAdminUser,)
    serializer_class = ProviderSerializer
    queryset = Provider.objects.all()
    filter_backends = (filters.DjangoFilterBackend,)
    filter_class = ProviderFilter

    @cache_response(key_func=CustomListKeyConstructor())
    def get(self, request, *args, **kwargs):
        return super(ProviderListBulkCreate, self).get(request, *args, **kwargs)



class ProviderRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = (permissions.IsAuthenticated, permissions.IsAdminUser,)
    serializer_class = ProviderSerializer
    queryset = Provider.objects.all()

    @cache_response(key_func=CustomObjectKeyConstructor())
    def get(self, request, *args, **kwargs):
        return super(ProviderRetrieveUpdateDestroy, self).get(request,
                                                              *args, **kwargs)
