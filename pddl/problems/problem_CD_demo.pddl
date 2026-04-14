(define (problem cd-demo)
  (:domain building-indoor)

  (:objects
    robot1 - robot
    cafeteria entrada_cd escaleras_p0 escaleras_pm1 gimnasio - ubicacion
    planta_m1 planta_0 - planta
  )

  (:init
    (= (total-cost) 0)
    (en robot1 entrada_cd)
    (abierto cafeteria)
    (abierto entrada_cd)
    (abierto escaleras_p0)
    (abierto escaleras_pm1)
    (abierto gimnasio)
    (en_planta cafeteria planta_0)
    (en_planta entrada_cd planta_0)
    (en_planta escaleras_p0 planta_0)
    (en_planta escaleras_pm1 planta_m1)
    (en_planta gimnasio planta_m1)
    (es_escalera escaleras_pm1)
    (es_escalera escaleras_p0)
    (conectado_pasillo entrada_cd cafeteria)
    (= (distancia entrada_cd cafeteria) 10)
    (conectado_pasillo cafeteria entrada_cd)
    (= (distancia cafeteria entrada_cd) 10)
    (conectado_pasillo entrada_cd escaleras_p0)
    (= (distancia entrada_cd escaleras_p0) 10)
    (conectado_pasillo escaleras_p0 entrada_cd)
    (= (distancia escaleras_p0 entrada_cd) 10)
    (conectado_pasillo cafeteria escaleras_p0)
    (= (distancia cafeteria escaleras_p0) 10)
    (conectado_pasillo escaleras_p0 cafeteria)
    (= (distancia escaleras_p0 cafeteria) 10)
    (conectado_pasillo escaleras_pm1 gimnasio)
    (= (distancia escaleras_pm1 gimnasio) 10)
    (conectado_pasillo gimnasio escaleras_pm1)
    (= (distancia gimnasio escaleras_pm1) 10)
    (conectado_escalera_subir escaleras_pm1 escaleras_p0)
    (conectado_escalera_bajar escaleras_p0 escaleras_pm1)
  )

  (:goal
    (en robot1 gimnasio)
  )

  (:metric minimize (total-cost))
)
