/*
Navicat MySQL Data Transfer

Source Server         : ConNube
Source Server Version : 80032
Source Host           : 144.217.81.168:3306
Source Database       : bd_databosquev3_vyn

Target Server Type    : MYSQL
Target Server Version : 80032
File Encoding         : 65001

Date: 2023-03-11 21:42:27
*/

SET FOREIGN_KEY_CHECKS=0;

-- ----------------------------
-- Table structure for provincias
-- ----------------------------
DROP TABLE IF EXISTS `provincias`;
CREATE TABLE `provincias` (
  `idProv` int NOT NULL AUTO_INCREMENT,
  `Provincia` varchar(50) NOT NULL,
  `idDepa` int NOT NULL,
  PRIMARY KEY (`idProv`),
  KEY `FK_idDepa_Prov` (`idDepa`),
  CONSTRAINT `provincias_ibfk_1` FOREIGN KEY (`idDepa`) REFERENCES `departamentos` (`idDepa`)
) ENGINE=InnoDB AUTO_INCREMENT=194 DEFAULT CHARSET=utf8mb3;

-- ----------------------------
-- Records of provincias
-- ----------------------------
INSERT INTO `provincias` VALUES ('1', 'CHACHAPOYAS', '1');
INSERT INTO `provincias` VALUES ('2', 'BAGUA', '1');
INSERT INTO `provincias` VALUES ('3', 'BONGARA', '1');
INSERT INTO `provincias` VALUES ('4', 'CONDORCANQUI', '1');
INSERT INTO `provincias` VALUES ('5', 'LUYA', '1');
INSERT INTO `provincias` VALUES ('6', 'RODRIGUEZ DE MENDOZA', '1');
INSERT INTO `provincias` VALUES ('7', 'UTCUBAMBA', '1');
INSERT INTO `provincias` VALUES ('8', 'HUARAZ', '2');
INSERT INTO `provincias` VALUES ('9', 'AIJA', '2');
INSERT INTO `provincias` VALUES ('10', 'ANTONIO RAYMONDI', '2');
INSERT INTO `provincias` VALUES ('11', 'ASUNCION', '2');
INSERT INTO `provincias` VALUES ('12', 'BOLOGNESI', '2');
INSERT INTO `provincias` VALUES ('13', 'CARHUAZ', '2');
INSERT INTO `provincias` VALUES ('14', 'CARLOS FERMIN FITZCARRALD', '2');
INSERT INTO `provincias` VALUES ('15', 'CASMA', '2');
INSERT INTO `provincias` VALUES ('16', 'CORONGO', '2');
INSERT INTO `provincias` VALUES ('17', 'HUARI', '2');
INSERT INTO `provincias` VALUES ('18', 'HUARMEY', '2');
INSERT INTO `provincias` VALUES ('19', 'HUAYLAS', '2');
INSERT INTO `provincias` VALUES ('20', 'MARISCAL LUZURIAGA', '2');
INSERT INTO `provincias` VALUES ('21', 'OCROS', '2');
INSERT INTO `provincias` VALUES ('22', 'PALLASCA', '2');
INSERT INTO `provincias` VALUES ('23', 'POMABAMBA', '2');
INSERT INTO `provincias` VALUES ('24', 'RECUAY', '2');
INSERT INTO `provincias` VALUES ('25', 'SANTA', '2');
INSERT INTO `provincias` VALUES ('26', 'SIHUAS', '2');
INSERT INTO `provincias` VALUES ('27', 'YUNGAY', '2');
INSERT INTO `provincias` VALUES ('28', 'ABANCAY', '3');
INSERT INTO `provincias` VALUES ('29', 'ANDAHUAYLAS', '3');
INSERT INTO `provincias` VALUES ('30', 'ANTABAMBA', '3');
INSERT INTO `provincias` VALUES ('31', 'AYMARAES', '3');
INSERT INTO `provincias` VALUES ('32', 'COTABAMBAS', '3');
INSERT INTO `provincias` VALUES ('33', 'CHINCHEROS', '3');
INSERT INTO `provincias` VALUES ('34', 'GRAU', '3');
INSERT INTO `provincias` VALUES ('35', 'AREQUIPA', '4');
INSERT INTO `provincias` VALUES ('36', 'CAMANA', '4');
INSERT INTO `provincias` VALUES ('37', 'CARAVELI', '4');
INSERT INTO `provincias` VALUES ('38', 'CASTILLA', '4');
INSERT INTO `provincias` VALUES ('39', 'CAYLLOMA', '4');
INSERT INTO `provincias` VALUES ('40', 'CONDESUYOS', '4');
INSERT INTO `provincias` VALUES ('41', 'ISLAY', '4');
INSERT INTO `provincias` VALUES ('42', 'LA UNION', '4');
INSERT INTO `provincias` VALUES ('43', 'HUAMANGA', '5');
INSERT INTO `provincias` VALUES ('44', 'CANGALLO', '5');
INSERT INTO `provincias` VALUES ('45', 'HUANCA SANCOS', '5');
INSERT INTO `provincias` VALUES ('46', 'HUANTA', '5');
INSERT INTO `provincias` VALUES ('47', 'LA MAR', '5');
INSERT INTO `provincias` VALUES ('48', 'LUCANAS', '5');
INSERT INTO `provincias` VALUES ('49', 'PARINACOCHAS', '5');
INSERT INTO `provincias` VALUES ('50', 'PAUCAR DEL SARA SARA', '5');
INSERT INTO `provincias` VALUES ('51', 'SUCRE', '5');
INSERT INTO `provincias` VALUES ('52', 'VICTOR FAJARDO', '5');
INSERT INTO `provincias` VALUES ('53', 'VILCAS HUAMAN', '5');
INSERT INTO `provincias` VALUES ('54', 'CAJAMARCA', '6');
INSERT INTO `provincias` VALUES ('55', 'CAJABAMBA', '6');
INSERT INTO `provincias` VALUES ('56', 'CELENDIN', '6');
INSERT INTO `provincias` VALUES ('57', 'CHOTA ', '6');
INSERT INTO `provincias` VALUES ('58', 'CONTUMAZA', '6');
INSERT INTO `provincias` VALUES ('59', 'CUTERVO', '6');
INSERT INTO `provincias` VALUES ('60', 'HUALGAYOC', '6');
INSERT INTO `provincias` VALUES ('61', 'JAEN', '6');
INSERT INTO `provincias` VALUES ('62', 'SAN IGNACIO', '6');
INSERT INTO `provincias` VALUES ('63', 'SAN MARCOS', '6');
INSERT INTO `provincias` VALUES ('64', 'SAN PABLO', '6');
INSERT INTO `provincias` VALUES ('65', 'SANTA CRUZ', '6');
INSERT INTO `provincias` VALUES ('66', 'CALLAO', '7');
INSERT INTO `provincias` VALUES ('67', 'CUSCO', '8');
INSERT INTO `provincias` VALUES ('68', 'ACOMAYO', '8');
INSERT INTO `provincias` VALUES ('69', 'ANTA', '8');
INSERT INTO `provincias` VALUES ('70', 'CALCA', '8');
INSERT INTO `provincias` VALUES ('71', 'CANAS', '8');
INSERT INTO `provincias` VALUES ('72', 'CANCHIS', '8');
INSERT INTO `provincias` VALUES ('73', 'CHUMBIVILCAS', '8');
INSERT INTO `provincias` VALUES ('74', 'ESPINAR', '8');
INSERT INTO `provincias` VALUES ('75', 'LA CONVENCION', '8');
INSERT INTO `provincias` VALUES ('76', 'PARURO', '8');
INSERT INTO `provincias` VALUES ('77', 'PAUCARTAMBO', '8');
INSERT INTO `provincias` VALUES ('78', 'QUISPICANCHI', '8');
INSERT INTO `provincias` VALUES ('79', 'URUBAMBA', '8');
INSERT INTO `provincias` VALUES ('80', 'HUANCAVELICA', '9');
INSERT INTO `provincias` VALUES ('81', 'ACOBAMBA', '9');
INSERT INTO `provincias` VALUES ('82', 'ANGARAES', '9');
INSERT INTO `provincias` VALUES ('83', 'CASTROVIRREYNA', '9');
INSERT INTO `provincias` VALUES ('84', 'CHURCAMPA', '9');
INSERT INTO `provincias` VALUES ('85', 'HUAYTARA', '9');
INSERT INTO `provincias` VALUES ('86', 'TAYACAJA', '9');
INSERT INTO `provincias` VALUES ('87', 'HUANUCO', '10');
INSERT INTO `provincias` VALUES ('88', 'AMBO', '10');
INSERT INTO `provincias` VALUES ('89', 'DOS DE MAYO', '10');
INSERT INTO `provincias` VALUES ('90', 'HUACAYBAMBA', '10');
INSERT INTO `provincias` VALUES ('91', 'HUAMALIES', '10');
INSERT INTO `provincias` VALUES ('92', 'LEONCIO PRADO', '10');
INSERT INTO `provincias` VALUES ('93', 'MARA&Ntilde;ON', '10');
INSERT INTO `provincias` VALUES ('94', 'PACHITEA', '10');
INSERT INTO `provincias` VALUES ('95', 'PUERTO INCA', '10');
INSERT INTO `provincias` VALUES ('96', 'LAURICOCHA', '10');
INSERT INTO `provincias` VALUES ('97', 'YAROWILCA', '10');
INSERT INTO `provincias` VALUES ('98', 'ICA', '11');
INSERT INTO `provincias` VALUES ('99', 'CHINCHA', '11');
INSERT INTO `provincias` VALUES ('100', 'NAZCA', '11');
INSERT INTO `provincias` VALUES ('101', 'PALPA', '11');
INSERT INTO `provincias` VALUES ('102', 'PISCO', '11');
INSERT INTO `provincias` VALUES ('103', 'HUANCAYO', '12');
INSERT INTO `provincias` VALUES ('104', 'CONCEPCION', '12');
INSERT INTO `provincias` VALUES ('105', 'CHANCHAMAYO', '12');
INSERT INTO `provincias` VALUES ('106', 'JAUJA', '12');
INSERT INTO `provincias` VALUES ('107', 'JUNIN', '12');
INSERT INTO `provincias` VALUES ('108', 'SATIPO', '12');
INSERT INTO `provincias` VALUES ('109', 'TARMA', '12');
INSERT INTO `provincias` VALUES ('110', 'YAULI', '12');
INSERT INTO `provincias` VALUES ('111', 'CHUPACA', '12');
INSERT INTO `provincias` VALUES ('112', 'TRUJILLO', '13');
INSERT INTO `provincias` VALUES ('113', 'ASCOPE', '13');
INSERT INTO `provincias` VALUES ('114', 'BOLIVAR', '13');
INSERT INTO `provincias` VALUES ('115', 'CHEPEN', '13');
INSERT INTO `provincias` VALUES ('116', 'JULCAN', '13');
INSERT INTO `provincias` VALUES ('117', 'OTUZCO', '13');
INSERT INTO `provincias` VALUES ('118', 'PACASMAYO', '13');
INSERT INTO `provincias` VALUES ('119', 'PATAZ', '13');
INSERT INTO `provincias` VALUES ('120', 'SANCHEZ CARRION', '13');
INSERT INTO `provincias` VALUES ('121', 'SANTIAGO DE CHUCO', '13');
INSERT INTO `provincias` VALUES ('122', 'GRAN CHIMU', '13');
INSERT INTO `provincias` VALUES ('123', 'VIRU', '13');
INSERT INTO `provincias` VALUES ('124', 'CHICLAYO', '14');
INSERT INTO `provincias` VALUES ('125', 'FERRE&Ntilde;AFE', '14');
INSERT INTO `provincias` VALUES ('126', 'LAMBAYEQUE', '14');
INSERT INTO `provincias` VALUES ('127', 'LIMA', '15');
INSERT INTO `provincias` VALUES ('128', 'BARRANCA', '15');
INSERT INTO `provincias` VALUES ('129', 'CAJATAMBO', '15');
INSERT INTO `provincias` VALUES ('130', 'CANTA', '15');
INSERT INTO `provincias` VALUES ('131', 'CA&Ntilde;ETE', '15');
INSERT INTO `provincias` VALUES ('132', 'HUARAL', '15');
INSERT INTO `provincias` VALUES ('133', 'HUAROCHIRI', '15');
INSERT INTO `provincias` VALUES ('134', 'HUAURA', '15');
INSERT INTO `provincias` VALUES ('135', 'OYON', '15');
INSERT INTO `provincias` VALUES ('136', 'YAUYOS', '15');
INSERT INTO `provincias` VALUES ('137', 'MAYNAS', '16');
INSERT INTO `provincias` VALUES ('138', 'ALTO AMAZONAS', '16');
INSERT INTO `provincias` VALUES ('139', 'LORETO', '16');
INSERT INTO `provincias` VALUES ('140', 'MARISCAL RAMON CASTILLA', '16');
INSERT INTO `provincias` VALUES ('141', 'REQUENA', '16');
INSERT INTO `provincias` VALUES ('142', 'UCAYALI', '16');
INSERT INTO `provincias` VALUES ('143', 'TAMBOPATA', '17');
INSERT INTO `provincias` VALUES ('144', 'MANU', '17');
INSERT INTO `provincias` VALUES ('145', 'TAHUAMANU', '17');
INSERT INTO `provincias` VALUES ('146', 'MARISCAL NIETO', '18');
INSERT INTO `provincias` VALUES ('147', 'GENERAL SANCHEZ CERRO', '18');
INSERT INTO `provincias` VALUES ('148', 'ILO', '18');
INSERT INTO `provincias` VALUES ('149', 'PASCO', '19');
INSERT INTO `provincias` VALUES ('150', 'DANIEL ALCIDES CARRION', '19');
INSERT INTO `provincias` VALUES ('151', 'OXAPAMPA', '19');
INSERT INTO `provincias` VALUES ('152', 'PIURA', '20');
INSERT INTO `provincias` VALUES ('153', 'AYABACA', '20');
INSERT INTO `provincias` VALUES ('154', 'HUANCABAMBA', '20');
INSERT INTO `provincias` VALUES ('155', 'MORROPON', '20');
INSERT INTO `provincias` VALUES ('156', 'PAITA', '20');
INSERT INTO `provincias` VALUES ('157', 'SULLANA', '20');
INSERT INTO `provincias` VALUES ('158', 'TALARA', '20');
INSERT INTO `provincias` VALUES ('159', 'SECHURA', '20');
INSERT INTO `provincias` VALUES ('160', 'PUNO', '21');
INSERT INTO `provincias` VALUES ('161', 'AZANGARO', '21');
INSERT INTO `provincias` VALUES ('162', 'CARABAYA', '21');
INSERT INTO `provincias` VALUES ('163', 'CHUCUITO', '21');
INSERT INTO `provincias` VALUES ('164', 'EL COLLAO', '21');
INSERT INTO `provincias` VALUES ('165', 'HUANCANE', '21');
INSERT INTO `provincias` VALUES ('166', 'LAMPA', '21');
INSERT INTO `provincias` VALUES ('167', 'MELGAR', '21');
INSERT INTO `provincias` VALUES ('168', 'MOHO', '21');
INSERT INTO `provincias` VALUES ('169', 'SAN ANTONIO DE PUTINA', '21');
INSERT INTO `provincias` VALUES ('170', 'SAN ROMAN', '21');
INSERT INTO `provincias` VALUES ('171', 'SANDIA', '21');
INSERT INTO `provincias` VALUES ('172', 'YUNGUYO', '21');
INSERT INTO `provincias` VALUES ('173', 'MOYOBAMBA', '22');
INSERT INTO `provincias` VALUES ('174', 'BELLAVISTA', '22');
INSERT INTO `provincias` VALUES ('175', 'EL DORADO', '22');
INSERT INTO `provincias` VALUES ('176', 'HUALLAGA', '22');
INSERT INTO `provincias` VALUES ('177', 'LAMAS', '22');
INSERT INTO `provincias` VALUES ('178', 'MARISCAL CACERES', '22');
INSERT INTO `provincias` VALUES ('179', 'PICOTA', '22');
INSERT INTO `provincias` VALUES ('180', 'RIOJA', '22');
INSERT INTO `provincias` VALUES ('181', 'SAN MARTIN', '22');
INSERT INTO `provincias` VALUES ('182', 'TOCACHE', '22');
INSERT INTO `provincias` VALUES ('183', 'TACNA', '23');
INSERT INTO `provincias` VALUES ('184', 'CANDARAVE', '23');
INSERT INTO `provincias` VALUES ('185', 'JORGE BASADRE', '23');
INSERT INTO `provincias` VALUES ('186', 'TARATA', '23');
INSERT INTO `provincias` VALUES ('187', 'TUMBES', '24');
INSERT INTO `provincias` VALUES ('188', 'CONTRALMIRANTE VILLAR', '24');
INSERT INTO `provincias` VALUES ('189', 'ZARUMILLA', '24');
INSERT INTO `provincias` VALUES ('190', 'CORONEL PORTILLO', '25');
INSERT INTO `provincias` VALUES ('191', 'ATALAYA', '25');
INSERT INTO `provincias` VALUES ('192', 'PADRE ABAD', '25');
INSERT INTO `provincias` VALUES ('193', 'PURUS', '25');
