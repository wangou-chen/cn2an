import re
from warnings import warn
from typing import Union

from proces import preprocess

from .an2cn import An2Cn
from .conf import NUMBER_CN2AN, UNIT_CN2AN, STRICT_CN_NUMBER, NORMAL_CN_NUMBER, NUMBER_LOW_AN2CN, UNIT_LOW_AN2CN


class Cn2An(object):
    def __init__(self) -> None:
        self.all_num = "".join(list(NUMBER_CN2AN.keys()))
        self.all_unit = "".join(list(UNIT_CN2AN.keys()))
        self.strict_cn_number = STRICT_CN_NUMBER
        self.normal_cn_number = NORMAL_CN_NUMBER
        self.check_key_dict = {
            "strict": "".join(self.strict_cn_number.values()) + "点负",
            "normal": "".join(self.normal_cn_number.values()) + "点负",
            "smart": "".join(self.normal_cn_number.values()) + "点负" + "01234567890.-"
        }
        self.pattern_dict = self.__get_pattern()
        self.ac = An2Cn()
        self.mode_list = ["strict", "normal", "smart"]
        self.yjf_pattern = re.compile(fr"^.*?[元圆][{self.all_num}]角([{self.all_num}]分)?$")
        self.pattern1 = re.compile(fr"^-?\d+(\.\d+)?[{self.all_unit}]?$")
        self.ptn_all_num = re.compile(f"^[{self.all_num}]+$")
        # "十?" is for special case "十一万三"
        self.ptn_speaking_mode = re.compile(f"^([{self.all_num}]{{0,2}}[{self.all_unit}])+[{self.all_num}]$")

    def cn2an(self, inputs: Union[str, int, float] = None, mode: str = "strict") -> Union[float, int]:
        """中文数字转阿拉伯数字

        :param inputs: 中文数字、阿拉伯数字、中文数字和阿拉伯数字
        :param mode: strict 严格，normal 正常，smart 智能
        :return: 阿拉伯数字
        """
        if inputs is not None or inputs == "":
            if mode not in self.mode_list:
                raise ValueError(f"mode 仅支持 {str(self.mode_list)} ！")

            # 将数字转化为字符串
            if not isinstance(inputs, str):
                inputs = str(inputs)

            # 数据预处理：
            # 1. 繁体转简体
            # 2. 全角转半角
            inputs = preprocess(inputs, pipelines=[
                "traditional_to_simplified",
                "full_angle_to_half_angle"
            ])

            # 特殊转化 廿
            inputs = inputs.replace("廿", "二十")

            # 检查输入数据是否有效
            sign, integer_data, decimal_data, is_all_num = self.__check_input_data_is_valid(inputs, mode)

            # smart 下的特殊情况
            if sign == 0:
                return integer_data
            else:
                if not is_all_num:
                    if decimal_data is None:
                        output = self.__integer_convert(integer_data)
                    else:
                        output = self.__integer_convert(integer_data) + self.__decimal_convert(decimal_data)
                        # fix 1 + 0.57 = 1.5699999999999998
                        output = round(output, len(decimal_data))
                else:
                    if decimal_data is None:
                        output = self.__direct_convert(integer_data)
                    else:
                        output = self.__direct_convert(integer_data) + self.__decimal_convert(decimal_data)
                        # fix 1 + 0.57 = 1.5699999999999998
                        output = round(output, len(decimal_data))
        else:
            raise ValueError("输入数据为空！")

        return sign * output

    def __get_pattern(self) -> dict:
        # 整数严格检查
        _0 = "[零]"
        _1_9 = "[一二三四五六七八九]"
        _10_99 = f"{_1_9}?[十]{_1_9}?"
        _1_99 = f"({_10_99}|{_1_9})"
        _100_999 = f"({_1_9}[百]([零]{_1_9})?|{_1_9}[百]{_10_99})"
        _1_999 = f"({_100_999}|{_1_99})"
        _1000_9999 = f"({_1_9}[千]([零]{_1_99})?|{_1_9}[千]{_100_999})"
        _1_9999 = f"({_1000_9999}|{_1_999})"
        _10000_99999999 = f"({_1_9999}[万]([零]{_1_999})?|{_1_9999}[万]{_1000_9999})"
        _1_99999999 = f"({_10000_99999999}|{_1_9999})"
        _100000000_9999999999999999 = f"({_1_99999999}[亿]([零]{_1_99999999})?|{_1_99999999}[亿]{_10000_99999999})"
        _1_9999999999999999 = f"({_100000000_9999999999999999}|{_1_99999999})"
        str_int_pattern = f"^({_0}|{_1_9999999999999999})$"
        nor_int_pattern = f"^({_0}|{_1_9999999999999999})$"

        str_dec_pattern = "^[零一二三四五六七八九]{0,15}[一二三四五六七八九]$"
        nor_dec_pattern = "^[零一二三四五六七八九]{0,16}$"

        for str_num in self.strict_cn_number.keys():
            str_int_pattern = str_int_pattern.replace(str_num, self.strict_cn_number[str_num])
            str_dec_pattern = str_dec_pattern.replace(str_num, self.strict_cn_number[str_num])
        for nor_num in self.normal_cn_number.keys():
            nor_int_pattern = nor_int_pattern.replace(nor_num, self.normal_cn_number[nor_num])
            nor_dec_pattern = nor_dec_pattern.replace(nor_num, self.normal_cn_number[nor_num])

        pattern_dict = {
            "strict": {
                "int": re.compile(str_int_pattern),
                "dec": re.compile(str_dec_pattern)
            },
            "normal": {
                "int": re.compile(nor_int_pattern),
                "dec": re.compile(nor_dec_pattern)
            }
        }
        return pattern_dict

    def __copy_num(self, num):
        cn_num = ""
        for n in num:
            cn_num += NUMBER_LOW_AN2CN[int(n)]
        return cn_num

    def __check_input_data_is_valid(self, check_data: str, mode: str) -> (int, str, str, bool):
        # 去除 元整、圆整、元正、圆正
        stop_words = ["元整", "圆整", "元正", "圆正"]
        for word in stop_words:
            if check_data[-2:] == word:
                check_data = check_data[:-2]

        # 去除 元、圆
        if mode != "strict":
            normal_stop_words = ["圆", "元"]
            for word in normal_stop_words:
                if check_data[-1] == word:
                    check_data = check_data[:-1]

        # 处理元角分
        result = self.yjf_pattern.search(check_data)
        if result:
            check_data = check_data.replace("元", "点").replace("角", "").replace("分", "")

        # 处理特殊问法：一千零十一 一万零百一十一
        if "零十" in check_data:
            check_data = check_data.replace("零十", "零一十")
        if "零百" in check_data:
            check_data = check_data.replace("零百", "零一百")

        for data in check_data:
            if data not in self.check_key_dict[mode]:
                raise ValueError(f"当前为{mode}模式，输入的数据不在转化范围内：{data}！")

        # 确定正负号
        if check_data[0] == "负":
            check_data = check_data[1:]
            sign = -1
        else:
            sign = 1

        if "点" in check_data:
            split_data = check_data.split("点")
            if len(split_data) == 2:
                integer_data, decimal_data = split_data
                # 将 smart 模式中的阿拉伯数字转化成中文数字
                if mode == "smart":
                    integer_data = re.sub(r"\d+", lambda x: self.ac.an2cn(x.group()), integer_data)
                    decimal_data = re.sub(r"\d+", lambda x: self.__copy_num(x.group()), decimal_data)
                    mode = "normal"
            else:
                raise ValueError("数据中包含不止一个点！")
        else:
            integer_data = check_data
            decimal_data = None
            # 将 smart 模式中的阿拉伯数字转化成中文数字
            if mode == "smart":
                # 10.1万 10.1
                result1 = self.pattern1.search(integer_data)
                if result1:
                    if result1.group() == integer_data:
                        if integer_data[-1] in UNIT_CN2AN.keys():
                            output = int(float(integer_data[:-1]) * UNIT_CN2AN[integer_data[-1]])
                        else:
                            output = float(integer_data)
                        return 0, output, None, None

                integer_data = re.sub(r"\d+", lambda x: self.ac.an2cn(x.group()), integer_data)
                mode = "normal"

        result_int = self.pattern_dict[mode]["int"].search(integer_data)
        if result_int:
            if result_int.group() == integer_data:
                if decimal_data is not None:
                    result_dec = self.pattern_dict[mode]["dec"].search(decimal_data)
                    if result_dec:
                        if result_dec.group() == decimal_data:
                            return sign, integer_data, decimal_data, False
                else:
                    return sign, integer_data, decimal_data, False
        else:
            if mode == "strict":
                raise ValueError(f"不符合格式的数据：{integer_data}")
            elif mode == "normal":
                # 纯数模式：一二三
                result_all_num = self.ptn_all_num.search(integer_data)
                if result_all_num:
                    if result_all_num.group() == integer_data:
                        if decimal_data is not None:
                            result_dec = self.pattern_dict[mode]["dec"].search(decimal_data)
                            if result_dec:
                                if result_dec.group() == decimal_data:
                                    return sign, integer_data, decimal_data, True
                        else:
                            return sign, integer_data, decimal_data, True

                # 口语模式：一万二，两千三，三百四，十三万六，一百二十五万三
                result_speaking_mode = self.ptn_speaking_mode.search(integer_data)
                if len(integer_data) >= 3 and result_speaking_mode and result_speaking_mode.group() == integer_data:
                    # len(integer_data)>=3: because the minimum length of integer_data that can be matched is 3
                    # to find the last unit
                    last_unit = result_speaking_mode.groups()[-1][-1]
                    _unit = UNIT_LOW_AN2CN[UNIT_CN2AN[last_unit] // 10]
                    integer_data = integer_data + _unit
                    if decimal_data is not None:
                        result_dec = self.pattern_dict[mode]["dec"].search(decimal_data)
                        if result_dec:
                            if result_dec.group() == decimal_data:
                                return sign, integer_data, decimal_data, False
                    else:
                        return sign, integer_data, decimal_data, False

        raise ValueError(f"不符合格式的数据：{check_data}")

    def __integer_convert(self, integer_data: str) -> int:
        # 核心逻辑：处理缺省零的关键在于理解单位的层级关系
        output_integer = 0
        # 用于临时存储当前段的数值（例如，在“万”之前的“一千一百”）
        current_value = 0
        # 记录遇到的最大单位，用于处理“万”、“亿”等大单位
        largest_unit_seen = 1

        # 定义单位层级，从大到小
        unit_hierarchy = [
            ('亿', 100000000),
            ('万', 10000),
            ('千', 1000),
            ('百', 100),
            ('十', 10)
        ]

        # 将字符串转换为字符列表以便处理
        chars = list(integer_data)
        i = 0
        length = len(chars)

        while i < length:
            char = chars[i]
            
            if char in NUMBER_CN2AN:
                # 当前字符是数字
                num = NUMBER_CN2AN[char]
                
                # 查看下一个字符是否是单位
                if i + 1 < length and chars[i + 1] in UNIT_CN2AN:
                    unit_char = chars[i + 1]
                    unit_value = UNIT_CN2AN[unit_char]
                    current_value += num * unit_value
                    i += 2  # 跳过数字和单位
                    
                    # 更新遇到的最大单位
                    if unit_value > largest_unit_seen:
                        largest_unit_seen = unit_value
                else:
                    # 单独的数字，没有跟随单位，默认为1倍
                    current_value += num
                    i += 1
                    
            elif char in UNIT_CN2AN:
                # 关键修复：处理缺省"一"的情况，如"千一"应该是1000 + 1 = 1001
                unit_value = UNIT_CN2AN[char]
                
                # 检查这是否是缺省"一"的情况（单位前面没有数字）
                if i == 0 or (i > 0 and chars[i - 1] not in NUMBER_CN2AN):
                    current_value += 1 * unit_value  # 缺省"一"，补上
                else:
                    # 单位前面有数字，但可能缺省了中间单位
                    current_value += unit_value
                    
                # 更新遇到的最大单位
                if unit_value > largest_unit_seen:
                    largest_unit_seen = unit_value
                i += 1
                
            else:
                i += 1

            # 检查是否需要将当前段的值加到总结果中（遇到大单位时）
            if i < length:
                next_char = chars[i] if i < length else None
                # 如果下一个字符是更大的单位或者是字符串结束，结算当前段
                if next_char and next_char in UNIT_CN2AN:
                    next_unit = UNIT_CN2AN[next_char]
                    if next_unit >= 10000:  # 万、亿等大单位
                        output_integer += current_value * next_unit
                        current_value = 0
                        i += 1  # 跳过大单位

        # 加上最后一段的值
        output_integer += current_value

        return output_integer


    def __decimal_convert(self, decimal_data: str) -> float:
        len_decimal_data = len(decimal_data)

        if len_decimal_data > 16:
            warn(f"注意：小数部分长度为 {len_decimal_data} ，将自动截取前 16 位有效精度！")
            decimal_data = decimal_data[:16]
            len_decimal_data = 16

        output_decimal = 0
        for index in range(len(decimal_data) - 1, -1, -1):
            unit_key = NUMBER_CN2AN[decimal_data[index]]
            output_decimal += unit_key * 10 ** -(index + 1)

        # 处理精度溢出问题
        output_decimal = round(output_decimal, len_decimal_data)

        return output_decimal

    def __direct_convert(self, data: str) -> int:
        output_data = 0
        for index in range(len(data) - 1, -1, -1):
            unit_key = NUMBER_CN2AN[data[index]]
            output_data += unit_key * 10 ** (len(data) - index - 1)

        return output_data