(define (problem csc-demo)
  (:domain building-indoor)

  (:objects
    robot1 - robot
    aula_csc_1 entrada_csc escaleras_p0 escaleras_p1 - ubicacion
    planta_0 planta_1 - planta
  )

  (:init
    (= (total-cost) 0)
    (en robot1 entrada_csc)
    (abierto aula_csc_1)
    (abierto entrada_csc)
    (abierto escaleras_p0)
    (abierto escaleras_p1)
    (en_planta aula_csc_1 planta_1)
    (en_planta entrada_csc planta_0)
    (en_planta escaleras_p0 planta_0)
    (en_planta escaleras_p1 planta_1)
    (es_escalera escaleras_p0)
    (es_escalera escaleras_p1)
    (conectado_pasillo entrada_csc escaleras_p0)
    (= (distancia entrada_csc escaleras_p0) 15)
    (conectado_pasillo escaleras_p0 entrada_csc)
    (= (distancia escaleras_p0 entrada_csc) 15)
    (conectado_pasillo aula_csc_1 escaleras_p1)
    (= (distancia aula_csc_1 escaleras_p1) 15)
    (conectado_pasillo escaleras_p1 aula_csc_1)
    (= (distancia escaleras_p1 aula_csc_1) 15)
    (conectado_escalera_subir escaleras_p0 escaleras_p1)
    (conectado_escalera_bajar escaleras_p1 escaleras_p0)
  )

  (:goal
    (en robot1 aula_csc_1)
  )

  (:metric minimize (total-cost))
)
