(define (problem h-demo)
  (:domain building-indoor)

  (:objects
    robot1 - robot
    aula_h_1 aula_h_2 entrada_h escaleras_p0 escaleras_p1 escaleras_p2 - ubicacion
    planta_0 planta_1 planta_2 - planta
  )

  (:init
    (= (total-cost) 0)
    (en robot1 entrada_h)
    (abierto aula_h_1)
    (abierto aula_h_2)
    (abierto entrada_h)
    (abierto escaleras_p0)
    (abierto escaleras_p1)
    (abierto escaleras_p2)
    (en_planta aula_h_1 planta_1)
    (en_planta aula_h_2 planta_2)
    (en_planta entrada_h planta_0)
    (en_planta escaleras_p0 planta_0)
    (en_planta escaleras_p1 planta_1)
    (en_planta escaleras_p2 planta_2)
    (es_escalera escaleras_p0)
    (es_escalera escaleras_p1)
    (es_escalera escaleras_p2)
    (conectado_pasillo entrada_h escaleras_p0)
    (= (distancia entrada_h escaleras_p0) 15)
    (conectado_pasillo escaleras_p0 entrada_h)
    (= (distancia escaleras_p0 entrada_h) 15)
    (conectado_pasillo aula_h_1 escaleras_p1)
    (= (distancia aula_h_1 escaleras_p1) 15)
    (conectado_pasillo escaleras_p1 aula_h_1)
    (= (distancia escaleras_p1 aula_h_1) 15)
    (conectado_pasillo aula_h_2 escaleras_p2)
    (= (distancia aula_h_2 escaleras_p2) 15)
    (conectado_pasillo escaleras_p2 aula_h_2)
    (= (distancia escaleras_p2 aula_h_2) 15)
    (conectado_escalera_subir escaleras_p0 escaleras_p1)
    (conectado_escalera_bajar escaleras_p1 escaleras_p0)
    (conectado_escalera_subir escaleras_p1 escaleras_p2)
    (conectado_escalera_bajar escaleras_p2 escaleras_p1)
  )

  (:goal
    (en robot1 aula_h_2)
  )

  (:metric minimize (total-cost))
)
