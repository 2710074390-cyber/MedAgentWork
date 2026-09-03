# -*- coding: utf-8 -*-
import json

M = "肝疾病、门静脉高压症、胆道疾病、胰腺疾病"
items = []

# ---------- A1 (24) ----------
items.append(dict(
 id="batch032_M4_A1_001", question_type="A1", module=M, bloom_level="记忆",
 question_text="关于肝小叶基本结构的描述，正确的是",
 options=["A. 中央为中央静脉","B. 中央为门静脉","C. 周边为中央静脉","D. 肝窦内流动的是动脉血","E. 胆小管由Kupffer细胞构成"],
 correct_answer="A",
 explanation="肝小叶中央是中央静脉，肝细胞索围绕其放射状排列；门静脉与肝动脉小分支血流汇合于肝窦；Kupffer细胞附着于肝窦壁；胆小管由相邻肝细胞胞膜凹陷形成。参阅教材P443。",
 source_page="教材P443", source_anchor="RAG/教材P443", difficulty_index=0.32, discrimination_index=0.42))

items.append(dict(
 id="batch032_M4_A1_002", question_type="A1", module=M, bloom_level="记忆",
 question_text="正常肝组织可耐受切除而不影响生理功能的肝实质比例约为",
 options=["A. 50%～60%","B. 60%～70%","C. 70%～80%","D. 80%～90%","E. 90%以上"],
 correct_answer="C",
 explanation="研究证明，切除正常肝实质的70%～80%仍可维持正常生理功能，且能再生至接近原肝重量，故局限性病变可施行肝段乃至更大范围切除。参阅教材P444。",
 source_page="教材P444", source_anchor="RAG/教材P444", difficulty_index=0.38, discrimination_index=0.40))

items.append(dict(
 id="batch032_M4_A1_003", question_type="A1", module=M, bloom_level="理解",
 question_text="细菌性肝脓肿最主要的细菌侵入途径是",
 options=["A. 胆道逆行上行","B. 门静脉播散","C. 肝动脉播散","D. 淋巴系统扩散","E. 开放性损伤直接侵入"],
 correct_answer="A",
 explanation="良性或恶性病变导致胆道梗阻并发生化脓性胆管炎时，细菌沿胆管上行，是引起细菌性肝脓肿的主要原因。参阅教材P445。",
 source_page="教材P445", source_anchor="RAG/教材P445", difficulty_index=0.45, discrimination_index=0.38))

items.append(dict(
 id="batch032_M4_A1_004", question_type="A1", module=M, bloom_level="理解",
 question_text="下列细菌中，较少作为细菌性肝脓肿常见致病菌的是",
 options=["A. 肺炎克雷伯菌","B. 大肠埃希菌","C. 厌氧链球菌","D. 金黄色葡萄球菌","E. 伤寒杆菌"],
 correct_answer="E",
 explanation="细菌性肝脓肿致病菌多为肺炎克雷伯菌、大肠埃希菌、厌氧链球菌、葡萄球菌等；伤寒杆菌并非其常见致病菌。参阅教材P445。",
 source_page="教材P445", source_anchor="RAG/教材P445", difficulty_index=0.50, discrimination_index=0.35))

items.append(dict(
 id="batch032_M4_A1_005", question_type="A1", module=M, bloom_level="理解",
 question_text="关于细菌性肝脓肿与阿米巴肝脓肿的鉴别，正确的是",
 options=["A. 细菌性多见于20～40岁","B. 阿米巴多见于50岁以上","C. 阿米巴脓液多为黄白色","D. 阿米巴多继发于胆道感染","E. 阿米巴多继发于阿米巴痢疾"],
 correct_answer="E",
 explanation="阿米巴肝脓肿多源于肠道阿米巴感染，绝大多数单发，继发于阿米巴痢疾后，少见糖尿病史；细菌性多继发于胆道感染，年龄多>50岁，脓液黄白色。参阅教材P446。",
 source_page="教材P446", source_anchor="RAG/教材P446", difficulty_index=0.55, discrimination_index=0.33))

items.append(dict(
 id="batch032_M4_A1_006", question_type="A1", module=M, bloom_level="记忆",
 question_text="棘球蚴病（包虫病）最常累及的器官是",
 options=["A. 肝脏","B. 肺脏","C. 脑","D. 肾脏","E. 脾脏"],
 correct_answer="A",
 explanation="肝包虫病临床上最常见，约占75%，其次为肺包虫病约占15%。参阅教材P447。",
 source_page="教材P447", source_anchor="RAG/教材P447", difficulty_index=0.40, discrimination_index=0.40))

items.append(dict(
 id="batch032_M4_A1_007", question_type="A1", module=M, bloom_level="记忆",
 question_text="根据中华医学会外科学分会分类，直径≤1cm的肝癌称为",
 options=["A. 微小肝癌","B. 小肝癌","C. 大肝癌","D. 巨大肝癌","E. 弥漫型肝癌"],
 correct_answer="A",
 explanation="分类为微小肝癌（直径≤1cm）、小肝癌（>1cm且≤5cm）、大肝癌（>5cm且≤10cm）、巨大肝癌（>10cm）。参阅教材P448。",
 source_page="教材P448", source_anchor="RAG/教材P448", difficulty_index=0.42, discrimination_index=0.38))

items.append(dict(
 id="batch032_M4_A1_008", question_type="A1", module=M, bloom_level="记忆",
 question_text="临床诊断原发性肝细胞癌时，甲胎蛋白（AFP）的诊断参考值通常要求",
 options=["A. ≥40ng/ml","B. ≥100ng/ml","C. ≥200ng/ml","D. ≥400ng/ml","E. ≥800ng/ml"],
 correct_answer="D",
 explanation="有肝炎或肝硬化病史，AFP≥400ng/ml，且超声/CT/MRI发现肝实质性肿块并具有典型影像学表现者，可作出临床诊断。参阅教材P448。",
 source_page="教材P448", source_anchor="RAG/教材P448", difficulty_index=0.45, discrimination_index=0.37))

items.append(dict(
 id="batch032_M4_A1_009", question_type="A1", module=M, bloom_level="理解",
 question_text="肝癌切除后总体5年生存率约为30%～40%，其中微小肝癌和小肝癌切除后5年生存率可达",
 options=["A. 40%以上","B. 50%以上","C. 60%以上","D. 75%以上","E. 90%以上"],
 correct_answer="D",
 explanation="肝癌切除后总体5年生存率为30%～40%，微小肝癌和小肝癌切除后5年生存率可达75%以上。参阅教材P449。",
 source_page="教材P449", source_anchor="RAG/教材P449", difficulty_index=0.48, discrimination_index=0.36))

items.append(dict(
 id="batch032_M4_A1_010", question_type="A1", module=M, bloom_level="应用",
 question_text="关于先天性肝囊肿的处理原则，正确的是",
 options=["A. 所有囊肿均需手术切除","B. 无症状小囊肿可定期观察","C. 囊肿均须穿刺引流","D. 多发性囊肿一律肝切除","E. 囊肿伴感染禁忌引流"],
 correct_answer="B",
 explanation="无症状的肝囊肿一般不需特殊处理；巨大且伴症状者可行穿刺引流或腹腔镜开窗术；伴感染、囊内出血者可穿刺引流或开窗术后置管。参阅教材P451。",
 source_page="教材P451", source_anchor="RAG/教材P451", difficulty_index=0.50, discrimination_index=0.34))

items.append(dict(
 id="batch032_M4_A1_011", question_type="A1", module=M, bloom_level="记忆",
 question_text="门静脉系统区别于体静脉的两大解剖特点是",
 options=["A. 位于两毛细血管网之间且无瓣膜","B. 位于两毛细血管网之间且有瓣膜","C. 有丰富瓣膜且压力高","D. 直接回流入右心房","E. 与肝动脉无交通"],
 correct_answer="A",
 explanation="门静脉系统位于两个毛细血管网之间，且门静脉系统内没有瓣膜，是其区别于体静脉的两大特点。参阅教材P452。",
 source_page="教材P452", source_anchor="RAG/教材P452", difficulty_index=0.40, discrimination_index=0.41))

items.append(dict(
 id="batch032_M4_A1_012", question_type="A1", module=M, bloom_level="理解",
 question_text="门静脉与腔静脉系统之间的交通支不包括",
 options=["A. 胃底、食管下段交通支","B. 直肠下端、肛管交通支","C. 前腹壁交通支","D. 腹膜后交通支","E. 脾静脉与左肾静脉交通支"],
 correct_answer="E",
 explanation="门静脉与腔静脉间有四个交通支：胃底食管下段、直肠下端肛管、前腹壁、腹膜后（Retzius静脉丛）。脾肾静脉交通支属于门体分流手术方式而非解剖交通支。参阅教材P453。",
 source_page="教材P453", source_anchor="RAG/教材P453", difficulty_index=0.52, discrimination_index=0.33))

items.append(dict(
 id="batch032_M4_A1_013", question_type="A1", module=M, bloom_level="理解",
 question_text="门静脉高压时四个交通支中最具临床意义、受压力差影响最早最显著的是",
 options=["A. 胃底、食管下段交通支","B. 直肠下端、肛管交通支","C. 前腹壁交通支","D. 腹膜后交通支","E. 肠系膜上、下静脉间交通支"],
 correct_answer="A",
 explanation="食管胃底交通支离门静脉主干和腔静脉最近，压力差最大，受门静脉高压影响最早、最显著，曲张静脉破裂可致致命性大出血。参阅教材P454。",
 source_page="教材P454", source_anchor="RAG/教材P454", difficulty_index=0.50, discrimination_index=0.35))

items.append(dict(
 id="batch032_M4_A1_014", question_type="A1", module=M, bloom_level="理解",
 question_text="Child-Pugh肝功能分级所依据的指标不包括",
 options=["A. 血清胆红素","B. 血浆白蛋白","C. 凝血酶原延长时间","D. 腹水与肝性脑病","E. 门静脉内径"],
 correct_answer="E",
 explanation="Child-Pugh分级项目为血清胆红素、血浆白蛋白、凝血酶原延长时间、腹水、肝性脑病；门静脉内径为影像学测量指标，不计入分级。参阅教材P455。",
 source_page="教材P455", source_anchor="RAG/教材P455", difficulty_index=0.55, discrimination_index=0.32))

items.append(dict(
 id="batch032_M4_A1_015", question_type="A1", module=M, bloom_level="记忆",
 question_text="门静脉高压症时，门静脉主干内径常达到",
 options=["A. ≥0.8cm","B. ≥1.0cm","C. ≥1.3cm","D. ≥1.5cm","E. ≥2.0cm"],
 correct_answer="C",
 explanation="门静脉高压症时门静脉内径常≥1.3cm，脾静脉内径常≥0.8cm。参阅教材P455。",
 source_page="教材P455", source_anchor="RAG/教材P455", difficulty_index=0.45, discrimination_index=0.38))

items.append(dict(
 id="batch032_M4_A1_016", question_type="A1", module=M, bloom_level="理解",
 question_text="经颈静脉肝内门体静脉分流术（TIPS）置入肝内支撑管的内径通常为",
 options=["A. 4～6mm","B. 8～12mm","C. 14～16mm","D. 18～20mm","E. 22～24mm"],
 correct_answer="B",
 explanation="TIPS经颈静脉在肝静脉与门静脉主要分支间建立通道并置入支架，内支撑管直径为8～12mm，可明显降低门静脉压力。参阅教材P456。",
 source_page="教材P456", source_anchor="RAG/教材P456", difficulty_index=0.55, discrimination_index=0.31))

items.append(dict(
 id="batch032_M4_A1_017", question_type="A1", module=M, bloom_level="记忆",
 question_text="在我国门静脉高压症外科治疗中应用最广泛的断流手术是",
 options=["A. 贲门周围血管离断术","B. 食管下端横断术","C. 胃底横断术","D. 胃周围血管缝扎术","E. 食管下端胃底切除术"],
 correct_answer="A",
 explanation="脾切除加贲门周围血管离断术最为常用，可较彻底阻断门-奇静脉间反常血流，又保存门静脉入肝血流；国内临床应用最广（约85%）。参阅教材P457。",
 source_page="教材P457", source_anchor="RAG/教材P457", difficulty_index=0.48, discrimination_index=0.36))

items.append(dict(
 id="batch032_M4_A1_018", question_type="A1", module=M, bloom_level="应用",
 question_text="门静脉高压症各类分流术中，术后肝性脑病发生率最高的是",
 options=["A. 远端脾-肾静脉分流术","B. 限制性门-腔静脉分流术","C. 非选择性门体分流术","D. 选择性门体分流术","E. 肠系膜上-下腔静脉桥式分流"],
 correct_answer="C",
 explanation="非选择性门体分流术将入肝门静脉血完全转流入体循环，肝性脑病发生率高达30%～50%，易引起肝衰竭；选择性分流肝性脑病发生率低。参阅教材P457。",
 source_page="教材P457", source_anchor="RAG/教材P457", difficulty_index=0.58, discrimination_index=0.30))

items.append(dict(
 id="batch032_M4_A1_019", question_type="A1", module=M, bloom_level="理解",
 question_text="巴德-吉亚利综合征（布-加综合征）的主要病变基础是",
 options=["A. 肝静脉和/或其开口以上下腔静脉阻塞","B. 门静脉主干血栓形成","C. 脾静脉闭塞","D. 肠系膜上静脉栓塞","E. 奇静脉回流受阻"],
 correct_answer="A",
 explanation="巴德-吉亚利综合征由先天或后天因素引起肝静脉和/或其开口以上的下腔静脉阻塞，以门静脉高压或门腔静脉高压为特征。参阅教材P458。",
 source_page="教材P458", source_anchor="RAG/教材P458", difficulty_index=0.55, discrimination_index=0.32))

items.append(dict(
 id="batch032_M4_A1_020", question_type="A1", module=M, bloom_level="理解",
 question_text="胆囊三角（Calot三角）内常穿过、胆道手术需特别注意避免损伤的结构是",
 options=["A. 胆囊动脉、肝右动脉、副右肝管","B. 门静脉主干","C. 肝总管","D. 胆总管","E. 胃十二指肠动脉"],
 correct_answer="A",
 explanation="胆囊三角由胆囊管、肝总管、肝下缘构成，胆囊动脉、肝右动脉、副右肝管常在此区穿过，胆道手术应特别注意避免损伤。参阅教材P461。",
 source_page="教材P461", source_anchor="RAG/教材P461", difficulty_index=0.52, discrimination_index=0.34))

items.append(dict(
 id="batch032_M4_A1_021", question_type="A1", module=M, bloom_level="理解",
 question_text="关于胆囊生理功能的描述，正确的是",
 options=["A. 容积30～60ml且可浓缩胆汁5～10倍","B. 容积100～150ml且不浓缩胆汁","C. 每日分泌胆汁800～1200ml","D. 仅储存胆汁不参与浓缩","E. 排空不受进食影响"],
 correct_answer="A",
 explanation="胆囊容积仅30～60ml，但24小时能接纳约500ml胆汁，黏膜吸收水电解质可将胆汁浓缩5～10倍；进食后CCK促使胆囊收缩排空。参阅教材P462。",
 source_page="教材P462", source_anchor="RAG/教材P462", difficulty_index=0.48, discrimination_index=0.37))

items.append(dict(
 id="batch032_M4_A1_022", question_type="A1", module=M, bloom_level="理解",
 question_text="我国胆囊结石中，胆固醇类结石所占比例约为",
 options=["A. 30%以上","B. 50%以上","C. 70%以上","D. 90%以上","E. 100%"],
 correct_answer="C",
 explanation="胆固醇类结石胆固醇含量超过70%，80%以上胆囊结石属于此类。参阅教材P468。",
 source_page="教材P468", source_anchor="RAG/教材P468", difficulty_index=0.46, discrimination_index=0.38))

items.append(dict(
 id="batch032_M4_A1_023", question_type="A1", module=M, bloom_level="应用",
 question_text="胆囊结石典型胆绞痛的诱发因素，不包括",
 options=["A. 饱餐","B. 进食油腻食物","C. 睡眠中体位改变","D. 长时间空腹平卧","E. 胆囊收缩或结石移位"],
 correct_answer="D",
 explanation="典型胆绞痛在饱餐、进食油腻食物后或睡眠中体位改变时发作，因胆囊收缩或结石移位嵌顿于壶腹部/颈部所致；长时间空腹平卧并非典型诱因。参阅教材P469。",
 source_page="教材P469", source_anchor="RAG/教材P469", difficulty_index=0.50, discrimination_index=0.35))

items.append(dict(
 id="batch032_M4_A1_024", question_type="A1", module=M, bloom_level="理解",
 question_text="肝外胆管结石合并胆管炎时出现的典型三联征（Charcot三联征）是指",
 options=["A. 腹痛、寒战高热、黄疸","B. 腹痛、休克、神经抑制","C. 腹痛、黄疸、休克","D. 寒战高热、黄疸、神经抑制","E. 腹痛、腹胀、黄疸"],
 correct_answer="A",
 explanation="肝外胆管结石造成胆管梗阻并继发胆管炎时，出现Charcot三联征：腹痛、寒战高热和黄疸。参阅教材P470。",
 source_page="教材P470", source_anchor="RAG/教材P470", difficulty_index=0.45, discrimination_index=0.40))

# ---------- A2 (6) ----------
items.append(dict(
 id="batch032_M4_A2_001", question_type="A2", module=M, bloom_level="应用",
 question_text="男性，52岁。寒战、高热2天，体温39.5℃，伴右上腹持续性胀痛、恶心。查体：右上腹压痛、肝区叩击痛，肝浊音界稍大。血常规：白细胞18×10^9/L，中性粒细胞0.88。超声示肝右叶单发液性暗区，直径约6cm。最可能的诊断是",
 options=["A. 细菌性肝脓肿","B. 阿米巴肝脓肿","C. 原发性肝癌","D. 胆囊结石伴胆囊炎","E. 右膈下脓肿"],
 correct_answer="A",
 explanation="寒战高热、肝区痛、肝大，白细胞及中性粒明显升高，超声示肝内液性暗区，符合细菌性肝脓肿；阿米巴者年龄较轻、脓液棕褐、血培养阴性。参阅教材P445。",
 source_page="教材P445", source_anchor="RAG/教材P445", difficulty_index=0.55, discrimination_index=0.33))

items.append(dict(
 id="batch032_M4_A2_002", question_type="A2", module=M, bloom_level="应用",
 question_text="男性，48岁。乙肝肝硬化病史10年。突发呕鲜红色血约800ml，查体：面色苍白，心率110次/分，血压90/60mmHg，腹壁见曲张静脉，脾肋下3cm。急诊内镜示食管胃底静脉曲张破裂出血。最合适的紧急处理首先是",
 options=["A. 急诊分流手术","B. 内镜下曲张静脉套扎术（EVL）","C. 立即脾切除","D. 肝移植","E. 开腹断流术"],
 correct_answer="B",
 explanation="食管胃底曲张静脉破裂出血，药物治疗无效时内镜下套扎术（EVL）是控制急性出血的首选方法，与药物联合成功率可达80%～100%；急诊手术病死率高，多用于严格治疗无效者。参阅教材P456。",
 source_page="教材P456", source_anchor="RAG/教材P456", difficulty_index=0.58, discrimination_index=0.31))

items.append(dict(
 id="batch032_M4_A2_003", question_type="A2", module=M, bloom_level="应用",
 question_text="女性，45岁。饱餐后突发右上腹阵发性绞痛，向右肩放射，伴恶心呕吐、轻度发热。查体：右上腹压痛，Murphy征阳性，未触及明显包块。超声示胆囊增大、壁厚（>4mm），腔内强回声伴声影。最可能的诊断是",
 options=["A. 急性结石性胆囊炎","B. 急性胆管炎","C. 急性胰腺炎","D. 消化性溃疡穿孔","E. 右肾结石"],
 correct_answer="A",
 explanation="饱餐油腻后右上腹痛、Murphy征阳性，超声见胆囊结石及胆囊壁增厚（>4mm）“双边征”，符合急性结石性胆囊炎；胆管炎应有黄疸及Charcot三联征。参阅教材P473。",
 source_page="教材P473", source_anchor="RAG/教材P473", difficulty_index=0.52, discrimination_index=0.34))

items.append(dict(
 id="batch032_M4_A2_004", question_type="A2", module=M, bloom_level="分析",
 question_text="男性，60岁。反复右上腹痛、寒战高热1周，今日出现神志淡漠、血压下降。查体：T39.8℃，P120次/分，BP85/50mmHg，皮肤巩膜黄染，剑突下压痛、轻度肌紧张。既往有胆管结石病史。最可能的诊断是",
 options=["A. 急性胆管炎","B. 急性梗阻性化脓性胆管炎（AOSC）","C. 急性胆囊炎","D. 急性胰腺炎","E. 肝脓肿"],
 correct_answer="B",
 explanation="在Charcot三联征（腹痛、寒战高热、黄疸）基础上出现休克与中枢神经系统受抑制，即Reynolds五联征，为急性梗阻性化脓性胆管炎（AOSC/ACST）的特征，病情凶险。参阅教材P475。",
 source_page="教材P475", source_anchor="RAG/教材P475", difficulty_index=0.58, discrimination_index=0.30))

items.append(dict(
 id="batch032_M4_A2_005", question_type="A2", module=M, bloom_level="应用",
 question_text="男性，38岁。饮酒后突发左上腹剧烈疼痛，向腰背部放射，伴频繁呕吐，呕吐后腹痛不缓解。查体：上腹压痛，肠鸣音减弱，轻度腹胀。血淀粉酶显著升高，超声见胆囊结石及胆管扩张。该急性胰腺炎最可能的病因是",
 options=["A. 胆源性（胆道结石）","B. 大量饮酒","C. 高脂血症","D. 药物性","E. 自身免疫性"],
 correct_answer="A",
 explanation="患者血淀粉酶升高、左上腹痛向腰背部放射、呕吐后不缓解，结合胆囊结石及胆管扩张，提示胆源性胰腺炎（占急性胰腺炎50%以上），结石经共同通道反流激活胰酶致病。参阅教材P527。",
 source_page="教材P527", source_anchor="RAG/教材P527", difficulty_index=0.56, discrimination_index=0.32))

items.append(dict(
 id="batch032_M4_A2_006", question_type="A2", module=M, bloom_level="应用",
 question_text="男性，65岁。进行性皮肤巩膜黄染1个月，伴消瘦、上腹隐痛。查体：巩膜黄染，可触及肿大胆囊、无压痛，肝肋下2cm。超声示胰头占位、肝内外胆管扩张。最可能的诊断是",
 options=["A. 胰头癌","B. 胆总管下端癌","C. 壶腹癌","D. 急性胆管炎","E. 胆囊结石"],
 correct_answer="A",
 explanation="胰头癌典型表现为进行性加重黄疸、Courvoisier征（胆囊肿大无压痛）、体重减轻；壶腹癌黄疸多波动性，胆总管下端癌胆囊常不肿大。参阅教材P494。",
 source_page="教材P494", source_anchor="RAG/教材P494", difficulty_index=0.55, discrimination_index=0.33))

# ---------- B1 (4 子题) ----------
portal_opts = ["A. 胃底、食管下段交通支","B. 直肠下端、肛管交通支","C. 前腹壁交通支","D. 腹膜后交通支","E. 肠系膜上、下静脉间交通支"]
items.append(dict(
 id="batch032_M4_B1_001", question_type="B1", module=M, bloom_level="记忆",
 question_text="B1型题：将正确答案的字母填入题干后方。\n共用选项：\nA. 胃底、食管下段交通支\nB. 直肠下端、肛管交通支\nC. 前腹壁交通支\nD. 腹膜后交通支\nE. 肠系膜上、下静脉间交通支\n子题1：门静脉与腔静脉间交通支中，离主干最近、压力差最大、最具临床意义的是：",
 options=portal_opts, correct_answer="A",
 explanation="食管胃底交通支离门静脉主干和腔静脉最近，压力差最大，受门静脉高压影响最早最显著，破裂可致致命大出血。参阅教材P453。",
 source_page="教材P453", source_anchor="RAG/教材P453", difficulty_index=0.45, discrimination_index=0.40))

items.append(dict(
 id="batch032_M4_B1_002", question_type="B1", module=M, bloom_level="记忆",
 question_text="B1型题：将正确答案的字母填入题干后方。\n共用选项：\nA. 胃底、食管下段交通支\nB. 直肠下端、肛管交通支\nC. 前腹壁交通支\nD. 腹膜后交通支\nE. 肠系膜上、下静脉间交通支\n子题2：门静脉血流经肠系膜下静脉、直肠上静脉与直肠下静脉吻合，可形成继发性痔，属于：",
 options=portal_opts, correct_answer="B",
 explanation="直肠下端、肛管交通支：门静脉经肠系膜下静脉、直肠上静脉与直肠下静脉、肛管静脉吻合流入下腔静脉，扩张可致继发性痔。参阅教材P453。",
 source_page="教材P453", source_anchor="RAG/教材P453", difficulty_index=0.45, discrimination_index=0.40))

sign_opts = ["A. Charcot三联征","B. Reynolds五联征","C. Murphy征","D. Courvoisier征","E. Grey-Turner征"]
items.append(dict(
 id="batch032_M4_B1_003", question_type="B1", module=M, bloom_level="记忆",
 question_text="B1型题：将正确答案的字母填入题干后方。\n共用选项：\nA. Charcot三联征\nB. Reynolds五联征\nC. Murphy征\nD. Courvoisier征\nE. Grey-Turner征\n子题3：肝外胆管结石合并胆管炎时的典型表现是：",
 options=sign_opts, correct_answer="A",
 explanation="肝外胆管结石造成梗阻并继发胆管炎时出现Charcot三联征：腹痛、寒战高热、黄疸。参阅教材P470。",
 source_page="教材P470", source_anchor="RAG/教材P470", difficulty_index=0.45, discrimination_index=0.40))

items.append(dict(
 id="batch032_M4_B1_004", question_type="B1", module=M, bloom_level="理解",
 question_text="B1型题：将正确答案的字母填入题干后方。\n共用选项：\nA. Charcot三联征\nB. Reynolds五联征\nC. Murphy征\nD. Courvoisier征\nE. Grey-Turner征\n子题4：胰头癌压迫胆总管致胆囊肿大、但触诊无压痛，称为：",
 options=sign_opts, correct_answer="D",
 explanation="胰头癌压迫或浸润胆总管所致进行性黄疸，胆囊肿大但无压痛，称库瓦西耶（Courvoisier）征，有助于胰头癌与胆管下段结石的鉴别。参阅教材P494。",
 source_page="教材P494", source_anchor="RAG/教材P494", difficulty_index=0.50, discrimination_index=0.36))

# ---------- X (8) ----------
items.append(dict(
 id="batch032_M4_X_001", question_type="X", module=M, bloom_level="应用",
 question_text="关于细菌性肝脓肿手术治疗的适应证，正确的有",
 options=["A. 脓肿较大、分隔较多","B. 已穿破进入胸腔或腹腔","C. 胆源性肝脓肿","D. 单发直径<3cm且已液化","E. 慢性肝脓肿"],
 correct_answer="ABCE",
 explanation="手术治疗适用于：脓肿较大、分隔较多；已穿破进入胸腔或腹腔；胆源性肝脓肿；慢性肝脓肿。单发小脓肿（3～5cm）多首选经皮穿刺置管引流而非手术。参阅教材P445。",
 source_page="教材P445", source_anchor="RAG/教材P445", difficulty_index=0.58, discrimination_index=0.30))

items.append(dict(
 id="batch032_M4_X_002", question_type="X", module=M, bloom_level="理解",
 question_text="门静脉高压症时，门-体交通支扩张可引起的表现包括",
 options=["A. 食管胃底静脉曲张","B. 继发性痔","C. 前腹壁静脉曲张（海蛇头）","D. 腹膜后Retzius丛曲张","E. 下肢静脉曲张"],
 correct_answer="ABCD",
 explanation="交通支扩张表现为：食管胃底静脉曲张、直肠上/下静脉丛扩张致痔、脐旁与腹上/下深静脉交通支扩张致前腹壁静脉曲张（海蛇头）、腹膜后Retzius丛曲张；下肢静脉曲张与本病无直接关系。参阅教材P454。",
 source_page="教材P454", source_anchor="RAG/教材P454", difficulty_index=0.52, discrimination_index=0.34))

items.append(dict(
 id="batch032_M4_X_003", question_type="X", module=M, bloom_level="应用",
 question_text="食管胃底曲张静脉破裂出血的非手术治疗措施包括",
 options=["A. 生长抑素持续静脉滴注","B. 内镜下曲张静脉套扎术（EVL）","C. 三腔二囊管压迫止血","D. 急诊门体分流术","E. 质子泵抑制剂"],
 correct_answer="ABCE",
 explanation="非手术治疗包括：补液输血、药物（生长抑素/奥曲肽、β受体拮抗剂等）、内镜治疗（EIS/EVL）、三腔二囊管压迫、TIPS及PPI等；急诊分流术属手术治疗，仅用于严格治疗无效者。参阅教材P456。",
 source_page="教材P456", source_anchor="RAG/教材P456", difficulty_index=0.55, discrimination_index=0.33))

items.append(dict(
 id="batch032_M4_X_004", question_type="X", module=M, bloom_level="记忆",
 question_text="肝外胆管结石合并急性胆管炎时，Charcot三联征的组成包括",
 options=["A. 腹痛","B. 寒战、高热","C. 黄疸","D. 休克","E. 中枢神经系统受抑"],
 correct_answer="ABC",
 explanation="Charcot三联征为腹痛、寒战高热、黄疸；在此基础上出现休克与神经抑制则为Reynolds五联征（AOSC）。参阅教材P470。",
 source_page="教材P470", source_anchor="RAG/教材P470", difficulty_index=0.45, discrimination_index=0.42))

items.append(dict(
 id="batch032_M4_X_005", question_type="X", module=M, bloom_level="理解",
 question_text="与胆囊癌发生相关的危险因素包括",
 options=["A. 胆囊结石直径>3cm","B. 瓷化（钙化）胆囊","C. 胆囊腺瘤","D. 胆管结石","E. 胆囊结石直径<1cm"],
 correct_answer="ABC",
 explanation="胆囊癌与胆囊结石（直径3cm结石癌变率为1cm结石的10倍）、完全钙化的瓷化胆囊、胆囊腺瘤、胆胰管合流异常、溃疡性结肠炎等相关；胆管结石主要关联胆管癌。参阅教材P482。",
 source_page="教材P482", source_anchor="RAG/教材P482", difficulty_index=0.55, discrimination_index=0.32))

items.append(dict(
 id="batch032_M4_X_006", question_type="X", module=M, bloom_level="理解",
 question_text="急性胰腺炎的常见致病危险因素包括",
 options=["A. 胆道疾病（胆石症）","B. 大量饮酒","C. 高脂血症","D. 医源性ERCP","E. 十二指肠溃疡"],
 correct_answer="ABCD",
 explanation="急性胰腺炎主要病因有胆道疾病（占50%以上）、饮酒、代谢性疾病（高脂血症、高钙血症）、十二指肠液反流、医源性ERCP（2%～10%）、药物、创伤等；十二指肠溃疡非其直接病因。参阅教材P527。",
 source_page="教材P527", source_anchor="RAG/教材P527", difficulty_index=0.50, discrimination_index=0.37))

items.append(dict(
 id="batch032_M4_X_007", question_type="X", module=M, bloom_level="分析",
 question_text="关于胰头癌临床表现的描述，正确的有",
 options=["A. 进行性加重的黄疸","B. 上腹痛向腰背部放射","C. Courvoisier征阳性","D. 脂肪泻为突出表现","E. 体重明显减轻"],
 correct_answer="ABCE",
 explanation="胰头癌表现为进行性黄疸、上腹痛向腰背部放射（胰性疼痛）、Courvoisier征阳性、体重减轻；脂肪泻是慢性胰腺炎的四联症之一，非胰头癌突出表现。参阅教材P494。",
 source_page="教材P494", source_anchor="RAG/教材P494", difficulty_index=0.58, discrimination_index=0.31))

# X_008 = 考研真题 GS-2019-163
items.append(dict(
 id="batch032_M4_X_008", question_type="X", module=M, bloom_level="记忆",
 question_text="胆囊结石可能发生的并发症有",
 options=["A. 梗阻性黄疸","B. 胰腺炎","C. 肠梗阻","D. 胆囊癌","E. 肝硬化"],
 correct_answer="ABCD",
 explanation="胆囊结石可经胆囊管进入胆总管引起梗阻性黄疸；小结石通过Oddi括约肌可致胆源性胰腺炎；大结石经瘘管入肠偶致胆石性肠梗阻；结石及炎症长期刺激可诱发胆囊癌。[源:考研真题 GS-2019-163]",
 source_page="教材P469", source_anchor="考研真题/GS-2019-163", difficulty_index=0.45, discrimination_index=0.40,
 kaoyan_origin={"gs_id":"GS-2019-163","year":2019,"source":"2019考研西综·第163题","mode":"原题"}))

# ---------- 自检 ----------
assert len(items)==42, len(items)
for it in items:
    assert set(it.keys()) >= {"id","question_type","module","bloom_level","question_text","options","correct_answer","explanation","source_page","source_anchor","difficulty_index","discrimination_index"}
    assert len(it["options"])==5
    if it["question_type"] in ("A1","A2","B1"):
        assert len(it["correct_answer"])==1
    else:
        assert 2<=len(it["correct_answer"])<=4
    assert all(c in "ABCDE" for c in it["correct_answer"])
    assert 0.30<=it["difficulty_index"]<=0.85
    assert 0.20<=it["discrimination_index"]<=0.50
    assert it["bloom_level"] in ("记忆","理解","应用","分析")

from collections import Counter
print("题型", Counter(i["question_type"] for i in items))
print("Bloom", Counter(i["bloom_level"] for i in items))

with open(r"C:/Users/38063/Desktop/MedAgentWork/中间产物/batch032/module4.json","w",encoding="utf-8") as f:
    json.dump(items, f, ensure_ascii=False, indent=0)
print("written", len(items))
