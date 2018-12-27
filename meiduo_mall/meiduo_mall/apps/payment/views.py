import os
from alipay import AliPay
from django.conf import settings
from django.shortcuts import render

# Create your views here.


# GET /orders/(?P<order_id>\d+)/payment/
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.models import OrderInfo
from payment.models import Payment


class PaymentView(APIView):
    """
    获取支付链接
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        user = request.user
        # order_id
        # 校验
        try:
            order = OrderInfo.objects.get(
                order_id=order_id,
                user=user,
                status=OrderInfo.ORDER_STATUS_ENUM['UNPAID'],
                pay_method=OrderInfo.PAY_METHODS_ENUM['ALIPAY']
            )
        except OrderInfo.DoesNotExist:
            return Response({'message': '订单信息有误'}, status=status.HTTP_400_BAD_REQUEST)

        # 向支付宝发起请求，获取支付链接参数
        alipay_client = AliPay(
            appid=settings.ALIPAY_APPID,
            app_notify_url=None,  # 默认回调url
            app_private_key_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "keys/app_private_key.pem"),
            alipay_public_key_path=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                "keys/alipay_public_key.pem"),  # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
            sign_type="RSA2",  # RSA 或者 RSA2
            debug=settings.ALIPAY_DEBUG  # 默认False  是否是沙箱环境
        )

        # 电脑网站支付，需要跳转到https://openapi.alipay.com/gateway.do? + order_string
        order_string = alipay_client.api_alipay_trade_page_pay(
            out_trade_no=order_id,  # 订单编号
            total_amount=str(order.total_amount),  # 总金额
            subject='美多商城订单%s' % order_id,
            return_url="http://www.meiduo.site:8080/pay_success.html",
            notify_url=None  # 可选, 不填则使用默认notify url
        )

        # 拼接支付链接网址
        alipay_url = settings.ALIPAY_URL + '?' + order_string

        # 返回
        return Response({'alipay_url': alipay_url})

class PaymentStatusView(APIView):
    def put(self, request):
        # 接收参数
        # 校验
        alipay_req_data = request.query_params # QueryDict
        if not alipay_req_data:
            return Response({'message': "缺少参数"}, status=status.HTTP_400_BAD_REQUEST)

        alipay_req_dict = alipay_req_data.dict()
        sign = alipay_req_dict.pop('sign')

        alipay_client = AliPay(
            appid=settings.ALIPAY_APPID,
            app_notify_url=None,  # 默认回调url
            app_private_key_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "keys/app_private_key.pem"),
            alipay_public_key_path=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                "keys/alipay_public_key.pem"),  # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
            sign_type="RSA2",  # RSA 或者 RSA2
            debug=settings.ALIPAY_DEBUG  # 默认False  是否是沙箱环境
        )

        # 返回验证结果，True False
        result = alipay_client.verify(alipay_req_dict, sign)

        if result:
            order_id = alipay_req_dict.get('out_trade_no')
            trade_id = alipay_req_dict.get('trade_no')
            # 保存数据
            #   保存支付结果数据Payment
            Payment.objects.create(
                order_id=order_id,
                trade_id=trade_id
            )
            #  修改订单状态
            OrderInfo.objects.filter(order_id=order_id).update(status=OrderInfo.ORDER_STATUS_ENUM['UNSEND'])
            return Response({'trade_id': trade_id})
        else:
            return Response({'message': '参数有误'}, status=status.HTTP_400_BAD_REQUEST)


