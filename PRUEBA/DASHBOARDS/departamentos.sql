/*
Navicat MySQL Data Transfer

Source Server         : ConNube
Source Server Version : 80032
Source Host           : 144.217.81.168:3306
Source Database       : bd_databosquev3_vyn

Target Server Type    : MYSQL
Target Server Version : 80032
File Encoding         : 65001

Date: 2023-03-11 21:43:02
*/

SET FOREIGN_KEY_CHECKS=0;

-- ----------------------------
-- Table structure for departamentos
-- ----------------------------
DROP TABLE IF EXISTS `departamentos`;
CREATE TABLE `departamentos` (
  `idDepa` int NOT NULL AUTO_INCREMENT,
  `Departamento` varchar(50) NOT NULL,
  PRIMARY KEY (`idDepa`)
) ENGINE=InnoDB AUTO_INCREMENT=26 DEFAULT CHARSET=utf8mb3;

-- ----------------------------
-- Records of departamentos
-- ----------------------------
INSERT INTO `departamentos` VALUES ('1', 'AMAZONAS');
INSERT INTO `departamentos` VALUES ('2', 'ANCASH');
INSERT INTO `departamentos` VALUES ('3', 'APURIMAC');
INSERT INTO `departamentos` VALUES ('4', 'AREQUIPA');
INSERT INTO `departamentos` VALUES ('5', 'AYACUCHO');
INSERT INTO `departamentos` VALUES ('6', 'CAJAMARCA');
INSERT INTO `departamentos` VALUES ('7', 'CALLAO');
INSERT INTO `departamentos` VALUES ('8', 'CUSCO');
INSERT INTO `departamentos` VALUES ('9', 'HUANCAVELICA');
INSERT INTO `departamentos` VALUES ('10', 'HUANUCO');
INSERT INTO `departamentos` VALUES ('11', 'ICA');
INSERT INTO `departamentos` VALUES ('12', 'JUNIN');
INSERT INTO `departamentos` VALUES ('13', 'LA LIBERTAD');
INSERT INTO `departamentos` VALUES ('14', 'LAMBAYEQUE');
INSERT INTO `departamentos` VALUES ('15', 'LIMA');
INSERT INTO `departamentos` VALUES ('16', 'LORETO');
INSERT INTO `departamentos` VALUES ('17', 'MADRE DE DIOS');
INSERT INTO `departamentos` VALUES ('18', 'MOQUEGUA');
INSERT INTO `departamentos` VALUES ('19', 'PASCO');
INSERT INTO `departamentos` VALUES ('20', 'PIURA');
INSERT INTO `departamentos` VALUES ('21', 'PUNO');
INSERT INTO `departamentos` VALUES ('22', 'SAN MARTIN');
INSERT INTO `departamentos` VALUES ('23', 'TACNA');
INSERT INTO `departamentos` VALUES ('24', 'TUMBES');
INSERT INTO `departamentos` VALUES ('25', 'UCAYALI');
