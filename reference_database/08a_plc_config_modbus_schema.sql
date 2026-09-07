-- 真实项目 Modbus 点位配置（用户提供 2026-08-05 导出）
SET NAMES utf8mb4;
CREATE DATABASE IF NOT EXISTS production_report_demo DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE production_report_demo;
SET FOREIGN_KEY_CHECKS=0;
DROP TABLE IF EXISTS `plc_config_modbus`;
CREATE TABLE `plc_config_modbus`  (
  `variable_id` bigint NOT NULL AUTO_INCREMENT COMMENT '变量ID，主键',
  `variable_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '变量名称',
  `variable_en_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '变量英文名称',
  `biz_type` tinyint NOT NULL COMMENT '业务分类：1=遥测(FC03)，2=遥信(FC02)',
  `host` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '设备 IP',
  `port` int NOT NULL COMMENT 'TCP 端口',
  `slave_id` tinyint UNSIGNED NOT NULL COMMENT '从站地址',
  `register_address` int NOT NULL COMMENT '寄存器地址，如 40001、10001',
  `is_active` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT '1' COMMENT '是否激活：0=禁用，1=启用',
  `create_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT '' COMMENT '创建者',
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT '' COMMENT '更新者',
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `remark` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '备注',
  PRIMARY KEY (`variable_id`) USING BTREE,
  INDEX `idx_biz_type`(`biz_type` ASC) USING BTREE,
  INDEX `idx_host_slave`(`host` ASC, `slave_id` ASC) USING BTREE,
  INDEX `idx_is_active`(`is_active` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 1568 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = 'Modbus 基础点位配置表' ROW_FORMAT = Dynamic;
