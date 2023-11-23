import datetime
import logging
import sys

import config
import login
import process
import privateCrypt

DATE_FORMAT = "%m/%d/%Y %H:%M:%S %p"
TODAY = datetime.date.today().strftime("%Y%m%d")
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s  %(filename)s : %(levelname)s  %(message)s',  # 定义输出log的格式
                    stream=sys.stdout,
                    datefmt=DATE_FORMAT)

print(r'''
**************************************
    i茅台自动预约开始
**************************************
''')

process.get_current_session_id()

# 校验配置文件是否存在
configs = login.config
if len(configs.sections()) == 0:
    logging.error("配置文件未找到配置")
    sys.exit(1)

aes_key = privateCrypt.get_aes_key()

s_content = ""
failure_detail = ""
success_count = 0
failure_count = 0

for section in configs.sections():
    if (configs.get(section, 'enddate') != 9) and (TODAY > configs.get(section, 'enddate')):
        continue
    mobile = privateCrypt.decrypt_aes_ecb(section, aes_key)
    mobile = mobile.replace(mobile[3:7], '****')
    province = configs.get(section, 'province')
    city = configs.get(section, 'city')
    token = privateCrypt.decrypt_aes_ecb(configs.get(section, 'token'), aes_key)
    userId = privateCrypt.decrypt_aes_ecb(configs.get(section, 'userid'), aes_key)
    lat = configs.get(section, 'lat')
    lng = configs.get(section, 'lng')

    p_c_map, source_data = process.get_map(lat=lat, lng=lng)

    process.UserId = userId
    process.TOKEN = token
    process.init_headers(user_id=userId, token=token, lng=lng, lat=lat)
    # 根据配置中，要预约的商品ID，城市 进行自动预约
    try:
        for item in config.ITEM_CODES:
            max_shop_id = process.get_location_count(province=province,
                                                     city=city,
                                                     item_code=item,
                                                     p_c_map=p_c_map,
                                                     source_data=source_data,
                                                     lat=lat,
                                                     lng=lng)
            # print(f'max shop id : {max_shop_id}')
            if max_shop_id == '0':
                continue
            shop_info = source_data.get(str(max_shop_id))
            title = config.ITEM_MAP.get(item)
            logging.info("----------------")
            shopInfo = f'商品:{title}; 门店:{shop_info["name"]}'
            logging.info(shopInfo)
            reservation_params = process.act_params(max_shop_id, item)
            # 核心预约步骤
            r_success, r_content = process.reservation(reservation_params, mobile)
            if not r_success:
                failure_count += 1
                failure_detail += "\n" + r_content
            else:
                success_count += 1
        # 领取小茅运和耐力值
        process.getUserEnergyAward(mobile)
    except BaseException as e:
        logging.error(e)
        failure_count += 1
        msg = f'{mobile}; {e};'
        failure_detail += "\n" + msg

s_content = f"今日自动申购成功{success_count}人次，失败{failure_count}人次"
logging.info(f'结果推送：{s_content},{failure_detail}')
# 推送消息
process.send_msg("i茅台今日自动申购完成", s_content)
if failure_detail != "":
    process.send_msg("失败记录明细", failure_detail)