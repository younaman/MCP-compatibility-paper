;; ========================
;; Go 定义
;; ========================

;; 普通函数定义
(function_declaration
  name: (identifier) @name
  parameters: (parameter_list) @params) @func_def

;; 方法定义（带接收者）
(method_declaration
  receiver: (parameter_list) @receiver
  name: (field_identifier) @name
  parameters: (parameter_list) @params) @method_def



