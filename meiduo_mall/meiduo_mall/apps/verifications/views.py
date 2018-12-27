import random

from django.http import HttpResponse
from django.shortcuts import render

# Create your views here.
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from meiduo_mall.libs.captcha.captcha import captcha
from django_redis import get_redis_connection

from meiduo_mall.utils.exceptions import logger
from verifications.serializer import ImageCodeCheckSerializer
from . import constants
from meiduo_mall.utils.yuntongxun.sms import CCP
from celery_tasks.sms.tasks import send_sms_code

class ImageCodeView(APIView):
    """
    图片验证码
    """
    def get(self,request,image_code_id):
    #生成图片验证码
        text, image = captcha.generate_captcha()
    #保存真是数据
        redis_conn = get_redis_connection('verify_codes')
        redis_conn.setex("img_%s" % image_code_id, constants.IMAGE_CODE_REDIS_EXPIRES, text)
    #返回图片
        return HttpResponse(image,content_type='image/jpg')

class SMSCodeView(GenericAPIView):
    """
    短信验证码
    传入参数：mobile,image_code_id,text
    """
    serializer_class = ImageCodeCheckSerializer
    def get(self,request,mobile):
        #校验参数  通过序列化器实现
        serializer = self.get_serializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        #生成短信验证码
        sms_code = '%06d' %random.randint(0,999999)
        #保存短信验证码  保存发送记录
        redis_conn = get_redis_connection('verify_codes')

        pl = redis_conn.pipeline()
        pl.setex('sms_%s' %mobile,constants.SMS_CODE_REDIS_EXPIRES,sms_code)
        pl.setex('send_flag_%s' %mobile,constants.SEND_SMS_CODE_INTERVAL,1)

        pl.execute()
        #发送信息


        expires = constants.SMS_CODE_REDIS_EXPIRES // 60
        send_sms_code.delay(mobile,[sms_code,expires],constants.SMS_CODE_TEMP_ID)

        return Response({"message": "OK"})

