;; ========================
;; Rust 定义查询
;; ========================

;; 普通函数定义
(function_item
  name: (identifier) @name
  parameters: (parameters) @params) @func_def

;; 结构体定义
(struct_item
  name: (type_identifier) @name) @struct_def

;; 枚举定义
(enum_item
  name: (type_identifier) @name) @enum_def

;; trait定义
(trait_item
  name: (type_identifier) @name) @trait_def



